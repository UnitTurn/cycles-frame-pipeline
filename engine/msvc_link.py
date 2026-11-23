"""Preserve Unicode paths when MSVC reads a UTF-8 Ninja response file on Windows."""
from contextlib import ExitStack
import codecs
from pathlib import Path
import subprocess
import sys
import tempfile


def main(command):
    with ExitStack() as temp_files:
        args = list(command)
        for index, arg in enumerate(args):
            if not arg.startswith('@'):
                continue
            path = Path(arg[1:])
            if not path.is_file():
                continue
            data = path.read_bytes()
            if data.isascii() or data.startswith((codecs.BOM_UTF8, codecs.BOM_UTF16_LE)):
                continue
            # Unmarked response files are interpreted using the Windows system code page by link.exe.
            content = data.decode('utf-8')
            with tempfile.NamedTemporaryFile(dir=path.parent, suffix='.rsp', delete=False) as stream:
                fixed = Path(stream.name)
                temp_files.callback(fixed.unlink, missing_ok=True)
                stream.write(content.encode('utf-16'))
            args[index] = '@' + str(fixed)
        return subprocess.call(args)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
