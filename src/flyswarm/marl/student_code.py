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
AGENT_TEMPLATE = '''import numpy as np

def act(observation, context=None):
    action = np.zeros(6, dtype=np.float32)

    # Turn toward the assigned objective and move forward.
    objective_angle = np.arctan2(observation[12], observation[13])
    action[0] = 0.5
    action[2] = np.clip(objective_angle, -1.0, 1.0)

    return action
'''
REWARD_TEMPLATE = '''"""Example: reward progress, useful damage, and keeping vehicles alive.

The components dictionary contains public events from the latest battle step.
This function returns one finite number for PPO to learn from.
"""

def calculate_reward(components):
    # Reward capturing an objective, then add a small bonus for damage.
    objective_reward = 3.0 * components["objective_capture"]
    damage_reward = 0.01 * components["damage_dealt"]

    # own_death is a positive count, so subtract it to discourage losses.
    loss_penalty = 4.0 * components["own_death"]

    return float(
        objective_reward
        + damage_reward
        - loss_penalty
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
    if not callable(function) and not (label == "agent" and callable(getattr(module, "act_team", None))):
        raise ValueError(f"{label}: define a callable {function_name}(...)")
    return module


def load_agent(path: str | Path) -> Callable[[np.ndarray, dict[str, Any]], np.ndarray]:
    module = load_student_module(path, "act", "agent")
    function = getattr(module, "act", None)
    team_function = getattr(module, "act_team", None)
    if not callable(function) and not callable(team_function):
        raise ValueError("agent.py: define act(observation, context=None) or act_team(observations, contexts)")
    try:
        signature = inspect.signature(function) if callable(function) else None
        supports_context = bool(signature and (len(signature.parameters) >= 2 or any(
            p.kind == inspect.Parameter.VAR_POSITIONAL for p in signature.parameters.values()
        )))
    except (TypeError, ValueError):
        supports_context = False

    def act(observation: np.ndarray, context: dict[str, Any]) -> np.ndarray:
        if not callable(function):
            raise ValueError("agent.py: act() is not defined; use the act_team() interface")
        safe_observation = np.asarray(observation, dtype=np.float32).copy()
        safe_observation.flags.writeable = False
        result = function(safe_observation, dict(context)) if supports_context else function(safe_observation)
        return validate_action(result)

    reset = getattr(module, "reset", None)
    if callable(reset):
        try:
            reset_signature = inspect.signature(reset)
            try:
                reset_signature.bind(seed=0)
                reset_with_keyword = True
            except TypeError:
                reset_signature.bind(0)
                reset_with_keyword = False
        except (TypeError, ValueError):
            reset_with_keyword = True

        def reset_agent(seed: int) -> None:
            if reset_with_keyword:
                reset(seed=int(seed))
            else:
                reset(int(seed))

        act.reset = reset_agent  # type: ignore[attr-defined]
    else:
        act.reset = None  # type: ignore[attr-defined]

    if callable(team_function):
        try:
            team_signature = inspect.signature(team_function)
            team_signature.bind([], [])
        except (TypeError, ValueError) as exc:
            raise ValueError("agent.py: act_team must accept (observations, contexts)") from exc

        def act_team(observations: list[np.ndarray], contexts: list[dict[str, Any]]) -> list[np.ndarray]:
            if len(observations) != len(contexts):
                raise ValueError("agent.py: observations and contexts must have the same number of agents")
            safe_observations = []
            for observation in observations:
                safe = np.asarray(observation, dtype=np.float32).copy()
                safe.flags.writeable = False
                safe_observations.append(safe)
            result = team_function(safe_observations, [dict(context) for context in contexts])
            try:
                actions = np.asarray(result, dtype=object)
            except (TypeError, ValueError) as exc:
                raise ValueError("agent.py: act_team must return one six-value action per agent") from exc
            if actions.shape != (len(observations), 6):
                raise ValueError(
                    f"agent.py: act_team must return shape ({len(observations)}, 6); got {actions.shape}"
                )
            return [validate_action(result[index], "act_team()") for index in range(len(observations))]

        act.act_team = act_team  # type: ignore[attr-defined]
    else:
        act.act_team = None  # type: ignore[attr-defined]
    return act


def validate_action(result: Any, function_name: str = "act()") -> np.ndarray:
    if isinstance(result, (list, tuple)) and any(isinstance(item, (bool, np.bool_)) for item in result):
        raise ValueError(f"{function_name} must return six numeric values")
    value = np.asarray(result)
    if value.shape != (6,):
        raise ValueError(
            f"{function_name} must return exactly 6 numeric values in order {ACTION_NAMES}; got shape {value.shape}"
        )
    if not np.issubdtype(value.dtype, np.number) or np.issubdtype(value.dtype, np.bool_):
        raise ValueError(f"{function_name} must return six numeric values")
    try:
        value = value.astype(np.float32)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{function_name} must return six numeric values") from exc
    if not np.isfinite(value).all():
        raise ValueError(f"{function_name} returned NaN or infinity")
    if np.any(value < -1.0) or np.any(value > 1.0):
        raise ValueError(f"{function_name} values must be in the range [-1, 1]")
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
        # Student projects may include ordinary sibling modules such as
        # helpers.py. Add that directory only inside the policy worker.
        project_directory = str(Path(path).expanduser().resolve().parent)
        if project_directory not in sys.path:
            sys.path.insert(0, project_directory)
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
                        if reset:reset(int(request.get("seed",0)))
                        actions=[]
                    else:
                        observations=request["observations"]
                        contexts=request["contexts"]
                        if len(observations)!=len(contexts):
                            raise ValueError("agent.py: observations and contexts must have the same number of agents")
                        team_function=getattr(agent,"act_team",None)
                        if team_function:
                            actions=team_function(observations,contexts)
                        else:
                            actions=[agent(obs,context) for obs,context in zip(observations,contexts)]
                connection.send({"ok":True,"actions":[x.tolist() for x in actions],"log":output.getvalue()[-12000:]})
            except BaseException:
                connection.send({"ok":False,"error":traceback.format_exc()[-20000:]})
    except BaseException:
        try:connection.send({"ok":False,"error":traceback.format_exc()[-20000:]})
        except (BrokenPipeError,EOFError,OSError):pass
    finally:
        connection.close()


def _student_reward_process(path: str, connection) -> None:
    """Persistent reward worker; each IPC request contains a whole world-step batch."""
    if os.name != "nt":
        try:
            os.setsid()
        except OSError:
            pass
    try:
        project_directory = str(Path(path).expanduser().resolve().parent)
        if project_directory not in sys.path:
            sys.path.insert(0, project_directory)
        calculate_reward = load_reward(path)
        connection.send({"ok": True, "message": "ready"})
        while True:
            request = connection.recv()
            if request.get("command") == "stop":
                break
            try:
                output = _TailBuffer()
                with redirect_stdout(output), redirect_stderr(output):
                    if request.get("command") == "reset":
                        reset = getattr(calculate_reward, "reset", None)
                        if reset:
                            reset(int(request.get("seed", 0)))
                        values = []
                    else:
                        values = [calculate_reward(item) for item in request["samples"]]
                connection.send({"ok": True, "rewards": values, "log": output.getvalue()})
            except BaseException:
                connection.send({"ok": False, "error": traceback.format_exc()[-20000:]})
    except BaseException:
        try:
            connection.send({"ok": False, "error": traceback.format_exc()[-20000:]})
        except (BrokenPipeError, EOFError, OSError):
            pass
    finally:
        connection.close()


DEFAULT_STUDENT_WORKER_STARTUP_TIMEOUT_SECONDS = 60.0


class ManagedStudentAgent:
    """Persistent isolated policy process with timeout and process-tree cleanup."""
    def __init__(self,path: str | Path,timeout_seconds: float=2.0,startup_timeout_seconds: float=DEFAULT_STUDENT_WORKER_STARTUP_TIMEOUT_SECONDS):
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
        if len(observations)!=len(contexts):
            raise ValueError("observations and contexts must have the same number of agents")
        self.connection.send({"command":"act","observations":[np.asarray(x,dtype=np.float32) for x in observations],"contexts":contexts})
        result=self._receive("calculating agent actions")
        if len(result.get("actions",[]))!=len(observations):raise ValueError("agent.py: act_team returned the wrong number of actions")
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


class ManagedStudentReward:
    """Run reward.py in one persistent worker, with one IPC batch per world step.

    This process boundary protects the backend event loop from a blocked reward
    call. It is not an OS security sandbox; student code still has the current
    user's filesystem and process permissions.
    """
    def __init__(self, path: str | Path, timeout_seconds: float = 2.0,
                 startup_timeout_seconds: float = DEFAULT_STUDENT_WORKER_STARTUP_TIMEOUT_SECONDS):
        self.timeout_seconds = float(timeout_seconds)
        context = mp.get_context("spawn")
        parent, child = context.Pipe(duplex=True)
        self.connection = parent
        self.process = context.Process(
            target=_student_reward_process,
            args=(str(Path(path).expanduser().resolve()), child),
            daemon=False,
        )
        self.process.start()
        child.close()
        try:
            self._receive("loading reward.py", float(startup_timeout_seconds))
        except BaseException:
            self.close()
            raise

    def _receive(self, operation: str, timeout_seconds: float | None = None) -> dict[str, Any]:
        timeout = self.timeout_seconds if timeout_seconds is None else float(timeout_seconds)
        if not self.connection.poll(timeout):
            self._terminate()
            raise TimeoutError(f"reward.py timed out while {operation} ({timeout:g}s limit)")
        try:
            result = self.connection.recv()
        except (EOFError, OSError) as exc:
            self._terminate()
            raise RuntimeError(f"reward.py process ended while {operation}") from exc
        if not result.get("ok"):
            raise RuntimeError(result.get("error", "reward.py failed"))
        log = result.get("log", "")
        if log:
            print(log, end="" if log.endswith("\n") else "\n")
        return result

    def calculate_batch(self, samples: list[dict[str, Any]]) -> list[float]:
        """Calculate all active agents' rewards with one request/response.

        Each sample is either the legacy components map or a public sample
        mapping containing ``components`` and optional step fields.
        """
        if not isinstance(samples, list):
            raise TypeError("reward batch must be a list of sample dictionaries")
        self.connection.send({"command": "calculate_batch", "samples": samples})
        result = self._receive("calculating a batched world-step reward")
        rewards = result.get("rewards", [])
        if len(rewards) != len(samples):
            raise ValueError("reward.py returned the wrong number of rewards for the batch")
        return rewards

    def reset(self, seed: int) -> None:
        self.connection.send({"command": "reset", "seed": int(seed)})
        self._receive("resetting the reward episode")

    def _terminate(self) -> None:
        if not self.process.is_alive():
            return
        if os.name == "nt":
            try:
                subprocess.run(["taskkill", "/PID", str(self.process.pid), "/T", "/F"],
                               capture_output=True, check=False, timeout=5)
            except (OSError, subprocess.SubprocessError):
                self.process.terminate()
        else:
            try:
                os.killpg(self.process.pid, signal.SIGTERM)
            except OSError:
                self.process.terminate()
        self.process.join(timeout=1)
        if self.process.is_alive():
            if os.name != "nt":
                try:
                    os.killpg(self.process.pid, signal.SIGKILL)
                except OSError:
                    self.process.kill()
            else:
                self.process.kill()
            self.process.join(timeout=1)

    def close(self) -> None:
        if self.process.is_alive():
            try:
                self.connection.send({"command": "stop"})
                self.process.join(timeout=1)
            except (BrokenPipeError, EOFError, OSError):
                pass
        if self.process.is_alive():
            self._terminate()
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def load_reward(path: str | Path) -> Callable[[dict[str, Any]], float]:
    module = load_student_module(path, "calculate_reward", "reward")
    function = module.calculate_reward
    try:
        signature = inspect.signature(function)
        accepts_kwargs = any(parameter.kind == inspect.Parameter.VAR_KEYWORD
                             for parameter in signature.parameters.values())
        optional_fields = ("observation", "action", "next_observation", "context")
        accepted_fields = {
            name for name in optional_fields
            if accepts_kwargs or name in signature.parameters
        }
    except (TypeError, ValueError):
        accepted_fields = set()

    def calculate(sample: dict[str, Any]) -> float:
        # Old callers pass the component map directly. The extended public
        # contract wraps it alongside optional public step data.
        if "components" in sample and isinstance(sample["components"], dict):
            components = sample["components"]
            keyword_values = {name: sample[name] for name in accepted_fields if name in sample}
        else:
            components = sample
            keyword_values = {}
        for name in ("observation", "action", "next_observation"):
            value = keyword_values.get(name)
            if value is not None:
                safe = np.asarray(value, dtype=np.float32).copy()
                safe.flags.writeable = False
                keyword_values[name] = safe
        result = function(dict(components), **keyword_values)
        if isinstance(result, (bool, np.bool_)) or not np.isscalar(result):
            raise ValueError("calculate_reward() must return one finite numeric scalar")
        value = float(result)
        if not math.isfinite(value):
            raise ValueError("calculate_reward() returned NaN or infinity")
        return value

    reset = getattr(module, "reset", None)
    if callable(reset):
        try:
            reset_signature = inspect.signature(reset)
            try:
                reset_signature.bind(seed=0)
                reset_with_keyword = True
            except TypeError:
                reset_signature.bind(0)
                reset_with_keyword = False
        except (TypeError, ValueError):
            reset_with_keyword = True

        def reset_reward(seed: int) -> None:
            if reset_with_keyword:
                reset(seed=int(seed))
            else:
                reset(int(seed))

        calculate.reset = reset_reward  # type: ignore[attr-defined]
    else:
        calculate.reset = None  # type: ignore[attr-defined]

    return calculate
