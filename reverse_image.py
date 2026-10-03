"""Local cover extraction shared by identification and browser search."""
import zipfile
from pathlib import Path
import app


def cover(path, index=0):
    with zipfile.ZipFile(app.filesystem_path(path)) as archive:
        images=sorted((i for i in archive.infolist() if i.filename.lower().endswith(('.jpg','.jpeg','.png','.webp'))),key=lambda i:i.filename)
        if not 0 <= index < min(5,len(images)) or images[index].file_size > 20_000_000:
            raise ValueError('Choose a suitable image among the first five archive images.')
        data=archive.read(images[index])
        extension=Path(images[index].filename).suffix.lower()
        mime={'.jpg':'image/jpeg','.jpeg':'image/jpeg','.png':'image/png','.webp':'image/webp'}[extension]
        return data,mime,extension
