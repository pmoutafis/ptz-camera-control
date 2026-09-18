name: Build PTZ Bridge Executables

on:
  push:
    branches: [ "main" ]
  workflow_dispatch:

jobs:
  build:
    name: Build Executable
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [windows-latest, macos-latest]

    steps:
    - name: Checkout repository
      uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.10'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install pyinstaller flask flask-cors opencv-python

    - name: Build Executable (Windows)
      if: matrix.os == 'windows-latest'
      run: |
        pyinstaller --onefile --noconsole bridge.py --name PTZ-Bridge-Windows

    - name: Build Executable (Mac)
      if: matrix.os == 'macos-latest'
      run: |
        pyinstaller --onefile bridge.py --name PTZ-Bridge-Mac

    - name: Upload Executable Artifact
      uses: actions/upload-artifact@v4
      with:
        name: PTZ-Bridge-${{ matrix.os }}
        path: dist/PTZ-Bridge-*
