import glob
from abc import ABC
from typing import List, Callable, Sequence, Iterator

import cv2
import numpy as np


class ImageSequence(ABC, Sequence[np.ndarray]):
    pass


class FileListImageSequence(ImageSequence):
    def __init__(self, file_paths: List[str], load_as_grayscale: bool = False) -> None:
        self._file_paths = file_paths
        self._convert_to_grayscale = load_as_grayscale

    def filter(self, filter_map: Callable[[str], bool]) -> 'FileListImageSequence':
        new_paths = [x for x in self._file_paths if filter_map(x)]
        return FileListImageSequence(new_paths, self._convert_to_grayscale)

    def file_name(self, index: int) -> str:
        return self._file_paths[index]

    def __getitem__(self, index):
        if isinstance(index, int):
            if self._convert_to_grayscale:
                img = cv2.imread(self._file_paths[index], cv2.IMREAD_GRAYSCALE)
            else:
                img = cv2.cvtColor(
                    cv2.imread(self._file_paths[index], cv2.IMREAD_COLOR),
                    cv2.COLOR_BGR2RGB
                )
            return img
        else:
            assert isinstance(index, slice)
            return FileListImageSequence(
                self._file_paths[index], self._convert_to_grayscale
            )

    def __reversed__(self) -> Iterator[np.ndarray]:
        return iter(FileListImageSequence(
            self._file_paths[::-1], self._convert_to_grayscale
        ))

    def __len__(self) -> int:
        return len(self._file_paths)


class GlobImageSequence(FileListImageSequence):
    def __init__(self, glob_path: str, recursive=False, load_as_grayscale=False) -> None:
        super().__init__(
            sorted(glob.glob(glob_path, recursive=recursive)),
            load_as_grayscale
        )
