# Release contract

## Permanent Open Day platform release policy

Open Day Windows installers and portable packages must never be published or
attached to a GitHub Release. Keep Windows CI validation if useful, but do not
create Windows release assets for Open Day. This is a durable project policy;
future task prompts do not authorize changing it.

Every completed user-facing application change must pass the relevant tests,
produce a fresh macOS arm64 application build and installable DMG, smoke-test
the installed app, create a new matching version/tag, publish a GitHub Release
with the install artifacts, and report the release URL and commit SHA.

Do not claim release success unless the GitHub Release was published. Do not
publish a build that failed validation or packaged-app smoke tests. If a required
build or check is blocked, keep the source changes, report the blocker and useful
diagnostic output, and leave the work explicitly incomplete. Never overwrite an
existing version or tag. Release from the requested working branch; do not merge
to `main` unless the user asks.

For this project, a macOS release is not complete with a Godot export alone:
include a relocatable Python backend, the needed runtime dependencies, the
applicable dataset setup instructions, a drag-and-drop DMG, a ZIP, and SHA-256
checksums. Test a copy of the app from the mounted DMG outside the checkout.
State signing/notarization status accurately. Do not bundle MaleCNS research
data until its license and redistribution terms have been verified.

The supported packaging entry point is
`.venv/bin/python tools/package_macos.py --build --version <semver>` on Apple
Silicon with the matching Godot export template installed. It builds the arm64
PyInstaller onedir runtime, bundles its support files, ad-hoc signs the complete
app when no Developer ID is available, and creates the versioned DMG, ZIP and
`SHA256SUMS.txt`. `build/FlySwarm.zip` is a Godot-only legacy export and must
never be treated as a release artifact. Verify the installed app copy from
outside the checkout and test the GUI MaleCNS folder picker/check before
tagging or publishing.
