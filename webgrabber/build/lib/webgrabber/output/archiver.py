# webgrabber/webgrabber/output/archiver.py

from pathlib import Path
import tarfile
import zipfile


def archive_output(output_path, archive_path):
    """
    Archive the output directory
    output_path: Path object of directory to archive
    archive_path: Path to save archive (with extension .zip or .tar.gz)
    """
    output_path = Path(output_path)
    archive_path = Path(archive_path)

    # Determine archive type from extension
    if archive_path.suffix == '.zip' or archive_path.name.endswith('.zip'):
        create_zip(output_path, archive_path)
    elif archive_path.name.endswith('.tar.gz') or archive_path.name.endswith('.tgz'):
        create_targz(output_path, archive_path)
    else:
        # Default to zip
        create_zip(output_path, archive_path)


def create_zip(source_dir, output_file):
    """Create a ZIP archive"""
    with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in source_dir.rglob('*'):
            if file_path.is_file():
                arcname = file_path.relative_to(source_dir)
                zipf.write(file_path, arcname)


def create_targz(source_dir, output_file):
    """Create a TAR.GZ archive"""
    with tarfile.open(output_file, 'w:gz') as tarf:
        for file_path in source_dir.rglob('*'):
            if file_path.is_file():
                arcname = file_path.relative_to(source_dir)
                tarf.add(file_path, arcname=arcname)