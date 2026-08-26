# Rifqi Edition Windows Portable

The portable package is designed for a no-install Windows workflow.

## User flow

1. Download `MoneyPrinterTurbo-Rifqi-Portable-Windows-*.7z` from the fork Releases page.
2. Extract it to a normal writable folder such as `D:\MoneyPrinterTurbo-Rifqi`.
3. Double-click `START_RIFQI.bat`.
4. The launcher creates `config.toml` from `config.example.toml` on first start if needed.
5. The Rifqi Edition WebUI opens locally in the browser.
6. Use `SETTINGS.bat` whenever provider/API credentials or advanced upstream settings need to be changed.

No separate Python, uv, pip, FFmpeg, or project dependency installation is expected for the portable package.

## How the package is built

`.github/workflows/build-rifqi-portable.yml` downloads the latest official MoneyPrinterTurbo Windows portable release and uses it as the trusted runtime base. It then mirrors the fork's `app` and `webui` source over that runtime, copies the Rifqi launchers and root entrypoints, removes any bundled `config.toml`, and validates the embedded Python runtime before publishing an archive.

This avoids trying to relocate a normal Windows virtual environment, which is less reliable than reusing the upstream portable runtime structure.

## Validation performed by CI

Before publishing, the builder checks that:

- `lib/python/python.exe` exists in the portable runtime;
- the Rifqi WebUI and hybrid services compile with that embedded Python;
- Streamlit and MoviePy import correctly from the portable environment;
- the hybrid scene planner can execute a basic smoke plan.

If any validation fails, no portable release is published.

## Release behavior

Relevant changes to `main` automatically create a versioned release named `rifqi-portable-build-N`. The archive is also retained as a GitHub Actions artifact for 30 days.

## Credentials

Real API keys are never bundled by CI. Each extracted portable copy starts with a fresh local `config.toml`. Keep that file private and do not commit it.
