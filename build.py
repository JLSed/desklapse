import os
import shutil
import subprocess
from pathlib import Path
import zipfile
import urllib.request
import re

FFMPEG_URL = "https://github.com/GyanD/codexffmpeg/releases/download/7.0.1/ffmpeg-7.0.1-essentials_build.zip"
NSIS_URL = "https://downloads.sourceforge.net/project/nsis/NSIS%203/3.08/nsis-3.08.zip"

def download_and_extract(url, target_zip, extract_to):
    if not target_zip.exists():
        print(f"Downloading {target_zip.name}...")
        urllib.request.urlretrieve(url, target_zip)
    else:
        print(f"{target_zip.name} already exists. Skipping download.")
        
    print(f"Extracting {target_zip.name}...")
    with zipfile.ZipFile(target_zip, 'r') as zip_ref:
        zip_ref.extractall(extract_to)

def get_version():
    root_dir = Path(__file__).resolve().parent
    init_file = root_dir / "src" / "__init__.py"
    if init_file.exists():
        with open(init_file, "r", encoding="utf-8") as f:
            match = re.search(r'__version__\s*=\s*[\'"]([^\'"]+)[\'"]', f.read())
            if match:
                return match.group(1)
    return "1.0.0"

def build_releases():
    print("Starting DeskLapse Dual Release Build...")
    root_dir = Path(__file__).resolve().parent
    version = get_version()
    print(f"Building Version: {version}")

    dist_dir = root_dir / "dist"
    build_dir = root_dir / "build"
    release_dir = dist_dir / "Release"
    portable_zip = dist_dir / f"DeskLapse_Portable_{version}.zip"
    installer_exe = dist_dir / f"DeskLapse_Setup_{version}.exe"

    # Step 1: Clean build environment
    print("\nCleaning up old builds...")
    if release_dir.exists():
        shutil.rmtree(release_dir)
    if portable_zip.exists():
        portable_zip.unlink()
    if installer_exe.exists():
        installer_exe.unlink()

    # Step 2: Download dependencies
    print("\nFetching external dependencies...")
    build_dir.mkdir(exist_ok=True)
    temp_ffmpeg_dir = build_dir / "ffmpeg_extract"
    download_and_extract(FFMPEG_URL, build_dir / "ffmpeg.zip", temp_ffmpeg_dir)
    
    nsis_dir = build_dir / "nsis"
    download_and_extract(NSIS_URL, build_dir / "nsis.zip", nsis_dir)

    # Locate the extracted ffmpeg.exe
    ffmpeg_exe = next(temp_ffmpeg_dir.rglob("ffmpeg.exe"), None)
    if not ffmpeg_exe:
        raise FileNotFoundError("Could not find ffmpeg.exe in extracted archive.")

    # Locate makensis.exe
    makensis_exe = next(nsis_dir.rglob("makensis.exe"), None)
    if not makensis_exe:
        raise FileNotFoundError("Could not find makensis.exe in extracted archive.")

    # Save ffmpeg to project bin folder so pyinstaller or zip copies it reliably
    proj_bin = root_dir / "bin"
    proj_bin.mkdir(exist_ok=True)
    shutil.copy2(ffmpeg_exe, proj_bin / "ffmpeg.exe")

    # Step 3: Run PyInstaller
    print("\nCompiling Python code into executable...")
    subprocess.run([
        "pyinstaller", 
        "--noconfirm", 
        "--onefile", 
        "--windowed", 
        "--name", "DeskLapse", 
        "--icon", "assets/desklapse_logo.ico",
        "--add-data", "assets;assets",
        "src/main.py"
    ], check=True)

    # Step 4: Assemble Portable Version
    print("\nAssembling release files...")
    release_dir.mkdir(parents=True, exist_ok=True)
    
    app_exe = dist_dir / "DeskLapse.exe"
    shutil.copy2(app_exe, release_dir / "DeskLapse.exe")
    
    bin_dir = release_dir / "bin"
    bin_dir.mkdir(exist_ok=True)
    shutil.copy2(ffmpeg_exe, bin_dir / "ffmpeg.exe")

    # Zip Portable Release
    print(f"\nZipping to {portable_zip.name}...")
    with zipfile.ZipFile(portable_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(release_dir):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(release_dir)
                zipf.write(file_path, arcname)

    # Step 5: Build NSIS Installer
    print("\nGenerating Setup Installer...")
    nsi_script_path = root_dir / "installer.nsi"
    
    nsis_code = f"""
    !define APPNAME "DeskLapse"
    !define APPVERSION "{version}"

    SetCompressor /SOLID lzma
    Icon "assets\\desklapse_logo.ico"
    UninstallIcon "assets\\desklapse_logo.ico"

    Name "${{APPNAME}}"
    OutFile "{installer_exe.resolve()}"
    InstallDir "$PROGRAMFILES\\${{APPNAME}}"

    RequestExecutionLevel admin

    Page directory
    Page instfiles

    Section "Install"
      SetOutPath "$INSTDIR"
      File "{app_exe.resolve()}"
      
      SetOutPath "$INSTDIR\\bin"
      File "{ffmpeg_exe.resolve()}"

      SetOutPath "$PROFILE\\Videos\\DeskLapse_Captures"

      CreateDirectory "$SMPROGRAMS\\${{APPNAME}}"
      CreateShortcut "$SMPROGRAMS\\${{APPNAME}}\\${{APPNAME}}.lnk" "$INSTDIR\\DeskLapse.exe"
      
      WriteUninstaller "$INSTDIR\\uninstall.exe"
      
      WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${{APPNAME}}" "DisplayName" "${{APPNAME}}"
      WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${{APPNAME}}" "UninstallString" '"$INSTDIR\\uninstall.exe"'
      WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${{APPNAME}}" "InstallLocation" "$INSTDIR"
    SectionEnd

    Section "Uninstall"
      RMDir /r "$INSTDIR"
      RMDir /r "$SMPROGRAMS\\${{APPNAME}}"
      DeleteRegKey HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${{APPNAME}}"
    SectionEnd
    """
    
    with open(nsi_script_path, "w", encoding="utf-8") as f:
        f.write(nsis_code.strip())

    # Compile the script
    subprocess.run([str(makensis_exe), str(nsi_script_path)], check=True)
    
    # Cleanup
    if nsi_script_path.exists():
        nsi_script_path.unlink()

    print(f"\nBuild complete!")
    print(f"PORTABLE:  {portable_zip}")
    print(f"INSTALLER: {installer_exe}")

if __name__ == "__main__":
    build_releases()
