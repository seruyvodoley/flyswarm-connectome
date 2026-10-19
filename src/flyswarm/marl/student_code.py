"""Public Python hooks for student strategies and reward functions.

Student code runs only in the MARL backend process, away from Godot's GUI.
This is process separation, not a security sandbox: imported Python can use the
permissions of the current user. The UI and course materials must warn before
running code that did not come from the student.
"""
from __future__ import annotations

import inspect
import io
import math
import multiprocessing as mp
import os
import signal
import subprocess
import sys
import traceback
import types
import uuid
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, Callable

import numpy as np

ACTION_NAMES = ("throttle", "brake", "steering", "turret", "elevation", "fire")
AGENT_TEMPLATE = '''"""Return six controls in the documented FlySwarm action order."""
import numpy as np

def act(observation, context=None):
    # observation is a NumPy vector; context contains only your own public ID
    # and episode counters. No hidden enemy state is provided.
    action = np.zeros(6, dtype=np.float32)
    action[0] = 0.5  # throttle
    return action
'''
REWARD_TEMPLATE = '''"""Calculate one agent's training reward from public event components."""

def calculate_reward(components):
    # Components are documented in docs/marl_python_api.md.
    return float(
        3.0 * components["objective_capture"]
        + 0.01 * components["damage_dealt"]
        - 4.0 * components["own_death"]
    )
'''


def load_student_module(path: str | Path, function_name: str, label: str) -> types.ModuleType:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"{label}: file not found: {source}")
    module_name = f"flyswarm_student_{label}_{uuid.uuid4().hex}"
    module = types.ModuleType(module_name)
    module.__file__ = str(source)
    module.__package__ = ""
    sys.modules[module_name] = module
    try:
        # Compile the current bytes directly. SourceFileLoader's timestamp
        # pyc cache can otherwise serve stale code after rapid editor saves.
        code = compile(source.read_bytes(), str(source), "exec")
        exec(code, module.__dict__)
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    function = getattr(module, function_name, None)
    if not callable(function):
        raise ValueError(f"{label}: define a callable {function_name}(...)")
    return module


def load_agent(path: str | Path) -> Callable[[np.ndarray, dict[str, Any]], np.ndarray]:
    module = load_student_module(path, "act", "agent")
    function = module.act
    try:
        signature = inspect.signature(function)
        supports_context = len(signature.parameters) >= 2 or any(
            p.kind == inspect.Parameter.VAR_POSITIONAL for p in signature.parameters.values()
        )
    except (TypeError, ValueError):
        supports_context = False

    def act(observation: np.ndarray, context: dict[str, Any]) -> np.ndarray:
        safe_observation = np.asarray(observation, dtype=np.float32).copy()
        safe_observation.flags.writeable = False
        result = function(safe_observation, dict(context)) if supports_context else function(safe_observation)
        return validate_action(result)

    reset = getattr(module, "reset", None)
    act.reset = reset if callable(reset) else None  # type: ignore[attr-defined]
    return act


def validate_action(result: Any) -> np.ndarray:
    value=np.asarray(result)
    if value.shape!=(6,):
        raise ValueError(f"act() must return exactly 6 numeric values in order {ACTION_NAMES}; got shape {value.shape}")
    try:value=value.astype(np.float32)
    except (TypeError,ValueError) as exc:raise ValueError("act() must return six numeric values") from exc
    if not np.isfinite(value).all():raise ValueError("act() returned NaN or infinity")
    if np.any(value < -1.0) or np.any(value > 1.0):raise ValueError("act() values must be in the range [-1, 1]")
    return value


class _TailBuffer:
    """Capture a bounded tail so repeated student prints cannot grow memory forever."""
    def __init__(self, limit: int = 12_000):
        self.limit = int(limit)
        self.value = ""

    def write(self, value: str) -> int:
        self.value = (self.value + str(value))[-self.limit:]
        return len(value)

    def flush(self) -> None:
        pass

    def getvalue(self) -> str:
        return self.value


def _student_agent_process(path: str, connection) -> None:
    """Long-lived worker: policy code cannot block the GUI or backend loop."""
    if os.name!="nt":
        try:os.setsid()
        except OSError:pass
    try:
        agent=load_agent(path)
        connection.send({"ok":True,"message":"ready"})
        while True:
            request=connection.recv()
            if request.get("command")=="stop":break
            try:
                output=_TailBuffer()
                with redirect_stdout(output),redirect_stderr(output):
                    if request.get("command")=="reset":
                        reset=getattr(agent,"reset",None)
                        if reset:reset(seed=int(request.get("seed",0)))
                        actions=[]
                    else:
                        actions=[agent(obs,context) for obs,context in zip(request["observations"],request["contexts"])]
                connection.send({"ok":True,"actions":[x.tolist() for x in actions],"log":output.getvalue()[-12000:]})
            except BaseException:
                connection.send({"ok":False,"error":traceback.format_exc()[-20000:]})
    except BaseException:
        try:connection.send({"ok":False,"error":traceback.format_exc()[-20000:]})
        except (BrokenPipeError,EOFError,OSError):pass
    finally:
        connection.close()


class ManagedStudentAgent:
    """Persistent isolated policy process with timeout and process-tree cleanup."""
    def __init__(self,path: str | Path,timeout_seconds: float=2.0,startup_timeout_seconds: float=15.0):
        self.timeout_seconds=float(timeout_seconds)
        self.startup_timeout_seconds=float(startup_timeout_seconds)
        context=mp.get_context("spawn")
        parent,child=context.Pipe(duplex=True)
        self.connection=parent
        self.process=context.Process(target=_student_agent_process,args=(str(Path(path).resolve()),child),daemon=False)
        self.process.start();child.close()
        try:self._receive("loading agent.py",self.startup_timeout_seconds)
        except BaseException:
            self.close()
            raise

    def _receive(self,operation:str,timeout_seconds:float|None=None):
        timeout=self.timeout_seconds if timeout_seconds is None else float(timeout_seconds)
        if not self.connection.poll(timeout):
            self._terminate()
            raise TimeoutError(f"agent.py timed out while {operation} ({timeout:g}s limit)")
        try:result=self.connection.recv()
        except (EOFError,OSError) as exc:
            self._terminate();raise RuntimeError(f"agent.py process ended while {operation}") from exc
        if not result.get("ok"):
            raise RuntimeError(result.get("error","agent.py failed"))
        log=result.get("log","")
        if log:print(log,end="" if log.endswith("\n") else "\n")
        return result

    def reset(self,seed:int):
        self.connection.send({"command":"reset","seed":int(seed)})
        self._receive("resetting the episode")

    def act_team(self,observations:list[np.ndarray],contexts:list[dict[str,Any]])->list[np.ndarray]:
        self.connection.send({"command":"act","observations":[np.asarray(x,dtype=np.float32) for x in observations],"contexts":contexts})
        result=self._receive("calculating agent actions")
        if len(result.get("actions",[]))!=len(observations):raise ValueError("agent.py returned the wrong number of actions")
        return [validate_action(x) for x in result["actions"]]

    def _terminate(self):
        if not self.process.is_alive():return
        if os.name=="nt":
            try:
                subprocess.run(["taskkill","/PID",str(self.process.pid),"/T","/F"],capture_output=True,check=False,timeout=5)
            except (OSError,subprocess.SubprocessError):self.process.terminate()
        else:
            try:os.killpg(self.process.pid,signal.SIGTERM)
            except OSError:self.process.terminate()
        self.process.join(timeout=1)
        if self.process.is_alive():
            if os.name!="nt":
                try:os.killpg(self.process.pid,signal.SIGKILL)
                except OSError:self.process.kill()
            else:self.process.kill()
            self.process.join(timeout=1)

    def close(self):
        if self.process.is_alive():
            try:
                self.connection.send({"command":"stop"})
                self.process.join(timeout=1)
            except (BrokenPipeError,EOFError,OSError):pass
        if self.process.is_alive():self._terminate()
        self.connection.close()

    def __enter__(self):return self
    def __exit__(self,*_):self.close()


def load_reward(path: str | Path) -> Callable[[dict[str, float]], float]:
    module = load_student_module(path, "calculate_reward", "reward")
    function = module.calculate_reward

    def calculate(components: dict[str, float]) -> float:
        result = function(dict(components))
        if isinstance(result, (bool, np.bool_)) or not np.isscalar(result):
            raise ValueError("calculate_reward() must return one finite numeric scalar")
        value = float(result)
        if not math.isfinite(value):
            raise ValueError("calculate_reward() returned NaN or infinity")
        return value

    return calculate
