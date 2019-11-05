import os
import pickle
from typing import Optional, List, Tuple

import cv2
import numpy as np
import torch.utils.data
import torchvision.datasets.utils as tv_data

from . import sequence, pair


class HPatchesPair(pair.HomographyPair):
    """Represents a stereo pair from HPatches"""

    def __init__(self: 'HPatchesPair', image_1: np.ndarray, image_2: np.ndarray, homography: np.ndarray,
                 seq_name: str, indices: Tuple[int, int]):
        name = "{0}: {1} {2}".format(seq_name, indices[0] + 1, indices[1] + 1)
        super().__init__(image_1, image_2, homography, name)


class HPatchesPairGenerator:
    """Generates pairs of stereo images from an HPatches Sequence"""

    def __init__(self, name: str, images: List[np.ndarray], homographies: List[np.ndarray]):
        self.name = name
        self.images = images
        self._homographies = homographies
        assert (len(self._homographies) == 5)
        self._pairs_order = [(i, j) for i in range(0, 6) for j in range(i + 1, 6)]

    @staticmethod
    def read_raw_folder(path: str, convert_to_grayscale: Optional[bool] = True) -> 'HPatchesPairGenerator':
        name = os.path.basename(path)
        images: List[np.ndarray] = list(iter(
            sequence.GlobImageSequence(
                os.path.join(path, "*.ppm"),
                convert_to_grayscale=convert_to_grayscale
            )
        ))
        homography_paths = [os.path.join(path, "H_1_{0}".format(i)) for i in range(2, 7)]
        homographies: List[np.ndarray] = [np.loadtxt(homography_path) for homography_path in homography_paths]
        return HPatchesPairGenerator(name, images, homographies)

    def downsample_in_place(self: 'HPatchesPairGenerator') -> None:
        for i in range(len(self.images)):
            self.images[i] = cv2.pyrDown(self.images[i])

        h_half = np.array([[.5, 0, 0], [0, 0.5, 0], [0, 0, 1]])
        h_double = np.array([[2, 0, 0], [0, 2, 0], [0, 0, 1]])

        for i in range(len(self._homographies)):
            self._homographies[i] = np.dot(
                h_half,
                np.dot(
                    self._homographies[i],
                    h_double,
                )
            )

    def _get_homography(self: 'HPatchesPairGenerator', index_1: int, index_2: int) -> np.ndarray:
        # Subtract 1 from indices since the first homography (linear index == 0) is (0, 1)
        if index_1 == 0:
            return self._homographies[index_2 - 1]  # hom. (0 -> index_2)
        else:
            return np.dot(
                self._homographies[index_2 - 1],  # hom. (0 -> index_2)
                np.linalg.inv(self._homographies[index_1 - 1])  # hom. (index_1 -> 0)
            )

    def __len__(self: 'HPatchesPairGenerator') -> int:
        return len(self._pairs_order)

    def __getitem__(self: 'HPatchesPairGenerator', linear_index: int) -> HPatchesPair:
        two_dim_index = self._pairs_order[linear_index]
        image_1 = self.images[two_dim_index[0]]
        image_2 = self.images[two_dim_index[1]]
        homography = self._get_homography(two_dim_index[0], two_dim_index[1])
        return HPatchesPair(image_1, image_2, homography, self.name, two_dim_index)


class HPatchesSequenceStereoPairs(torch.utils.data.Dataset):
    """Loads the HPatches sequences dataset and returns stereo pairs of images from each sequence"""

    url: str = 'http://icvl.ee.ic.ac.uk/vbalnt/hpatches/hpatches-sequences-release.tar.gz'
    pairs_per_sequence: int = 15  # 6 choose 2 pairs
    train_sequences: List[str] = ["v_there", "i_yellowtent", "i_boutique", "v_wapping", "i_leuven", "i_school",
                                  "i_crownnight", "v_artisans", "v_colors", "i_ski", "v_circus", "v_tempera",
                                  "v_london", "v_war", "i_parking", "v_bark", "v_charing", "i_indiana", "v_weapons",
                                  "v_wormhole", "v_maskedman", "v_dirtywall", "v_wall", "v_vitro", "i_nuts",
                                  "i_londonbridge", "i_pool", "i_pinard", "i_greentea", "v_calder", "i_lionday",
                                  "i_crownday", "i_kions", "v_posters", "i_dome", "v_machines", "v_laptop", "v_boat",
                                  "v_churchill", "i_pencils", "v_beyus", "v_sunseason", "v_samples", "v_cartooncity",
                                  "v_gardens", "v_bip", "v_home", "i_veggies", "i_nescafe", "v_wounded", "i_toy",
                                  "v_dogman", "i_duda", "i_contruction", "v_graffiti", "i_gonnenberg", "v_astronautis",
                                  "i_ktirio", "i_castle", "i_greenhouse", "i_fenis", "i_partyfood", "v_adam",
                                  "v_apprentices", "v_blueprint", "i_smurf", "i_objects", "v_bird", "i_melon",
                                  "v_grace", "i_miniature", "v_bricks", "i_chestnuts", "i_village", "i_steps", "i_dc"]
    test_sequences: List[str] = ["i_ajuntament", "i_resort", "i_table", "i_troulos", "i_bologna", "i_lionnight",
                                 "i_porta", "i_zion", "i_brooklyn", "i_fruits", "i_books", "i_bridger",
                                 "i_whitebuilding", "i_kurhaus", "i_salon", "i_autannes", "i_tools", "i_santuario",
                                 "i_fog", "i_nijmegen", "v_courses", "v_coffeehouse", "v_abstract", "v_feast",
                                 "v_woman", "v_talent", "v_tabletop", "v_bees", "v_strand", "v_fest", "v_yard",
                                 "v_underground", "v_azzola", "v_eastsouth", "v_yuri", "v_soldiers", "v_man",
                                 "v_pomegranate", "v_birdwoman", "v_busstop"]

    @property
    def raw_folder(self: 'HPatchesSequenceStereoPairs') -> str:
        return os.path.join(self.root_folder, self.__class__.__name__, 'raw')

    @property
    def raw_extracted_folder(self: 'HPatchesSequenceStereoPairs') -> str:
        return os.path.join(self.raw_folder, "hpatches-sequences-release")

    @property
    def processed_folder(self: 'HPatchesSequenceStereoPairs') -> str:
        return os.path.join(self.root_folder, self.__class__.__name__, 'processed')

    @property
    def processed_file(self: 'HPatchesSequenceStereoPairs') -> str:
        file_name = "hpatches-"
        if self.downsample_large_images:
            file_name += "downsampled-"
        if self.convert_to_grayscale:
            file_name += "grayscale-"
        if self.require_pose_changes:
            file_name += "view-change-"
        if self.train:
            file_name += "training-"
        else:
            file_name += "testing-"
        file_name += "sequences.pickle"

        return os.path.join(self.processed_folder, file_name)

    def __init__(self: 'HPatchesSequenceStereoPairs', root: str,
                 train: Optional[bool] = True,
                 download: Optional[bool] = False,
                 require_pose_changes: Optional[bool] = True,
                 downsample_large_images: Optional[bool] = True,
                 convert_to_grayscale: Optional[bool] = True) -> None:
        self.root_folder = root
        self.train = train
        self.require_pose_changes = require_pose_changes
        self.downsample_large_images = downsample_large_images
        self.convert_to_grayscale = convert_to_grayscale

        if download:
            self.download()

        if not self._check_processed_exists():
            raise RuntimeError('Dataset not found.' +
                               ' You can use download=True to download it')

        with open(self.processed_file, 'rb') as pickle_file:
            self.sequences = pickle.load(pickle_file)
        return

    def __len__(self: 'HPatchesSequenceStereoPairs') -> int:
        return self.pairs_per_sequence * len(self.sequences)

    def __getitem__(self: 'HPatchesSequenceStereoPairs', index: int) -> HPatchesPair:
        return self.sequences[index // self.pairs_per_sequence][index % self.pairs_per_sequence]

    def download(self: 'HPatchesSequenceStereoPairs') -> None:

        if not self._check_raw_exists():
            os.makedirs(self.raw_folder, exist_ok=True)

            tv_data.download_and_extract_archive(
                HPatchesSequenceStereoPairs.url, download_root=self.raw_folder, remove_finished=True
            )

        if not self._check_processed_exists():

            if self.train:
                hpatches_folders = HPatchesSequenceStereoPairs.train_sequences
            else:
                hpatches_folders = HPatchesSequenceStereoPairs.test_sequences

            if self.require_pose_changes:
                hpatches_folders = [seq_folder for seq_folder in hpatches_folders if seq_folder.startswith('v_')]

            hpatches_folders = [
                os.path.join(self.raw_extracted_folder, seq_folder) for seq_folder in hpatches_folders
            ]

            sequences = [
                HPatchesPairGenerator.read_raw_folder(seq_folder, self.convert_to_grayscale) for seq_folder in
                hpatches_folders
            ]

            # IMIPS downscales larges images
            if self.downsample_large_images:
                for seq in sequences:
                    while np.any(np.array(seq.images[0].shape) > 1000):
                        seq.downsample_in_place()

            os.makedirs(self.processed_folder, exist_ok=True)
            with open(self.processed_file, 'wb') as pickle_file:
                pickle.dump(sequences, pickle_file)

    def _check_raw_exists(self: 'HPatchesSequenceStereoPairs') -> bool:
        return os.path.exists(self.raw_extracted_folder)

    def _check_processed_exists(self: 'HPatchesSequenceStereoPairs') -> bool:
        return os.path.exists(self.processed_file)
