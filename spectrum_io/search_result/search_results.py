import logging
import re
from abc import abstractmethod
from pathlib import Path
from typing import Dict, Optional, Tuple, Union

import pandas as pd

from spectrum_io.file import csv

logger = logging.getLogger(__name__)


def filter_valid_prosit_sequences(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filter valid Prosit sequences.

    :param df: df to filter
    :return: df after filtering out unsupported peptides
    """
    logger.info(f"#sequences before filtering for valid prosit sequences: {len(df.index)}")
    # retain only peptides that fall within [7, 30] length supported by Prosit
    df = df[(df["PEPTIDE_LENGTH"] <= 30) & (df["PEPTIDE_LENGTH"] >= 7)]
    # remove unsupported mods to exclude
    supported_pattern = re.compile(r"^(?:\[UNIMOD:\d+\]\-)?(?:[ACDEFGHIKLMNPQRSTVWY]+(?:\[UNIMOD:\d+\])?)*$")
    df = df[df["MODIFIED_SEQUENCE"].str.contains(supported_pattern)] 
    # remove non-canonical aas
    df = df[(~df["SEQUENCE"].str.contains("U|O"))]
    # remove precursor charges greater than 6
    df = df[df["PRECURSOR_CHARGE"] <= 6]
    logger.info(f"#sequences after filtering for valid prosit sequences: {len(df.index)}")

    return df


def parse_mods(mods: Dict[str, int]) -> Dict[str, str]:
    """
    Parse provided mapping of custom modification pattern to ProForma standard.

    This function takes a dictionary mapping custom modification pattern for specific aminoacids (keys) to a
    UNIMOD ID (values). The pattern is translated to ProForma standard and a new dictionary mapping the custom
    modification patterns to the ProForma standard is returned.
    The pattern for the custom modifications must start with the one-letter code for an aminoacid or '^' / '$',
    to describe n- / c-terminal modifications, respectively, followed by an optional pattern (which can be
    empty).
    This means that 'X'  or 'X(custom_pattern)', is both mapped to 'X[UNIMOD:#]'.
    For the n-terminus, an additional dash will be added automatically, which maps 'X(custom_pattern)' to
    'X[UNIMOD:#]-'. If the sequence to apply the transformation on already contains the dash, it needs to be part
    of the custom_pattern (i.e. 'X(custom_pattern)-'), to avoid adding an additional dash.

    :param mods: Dictionary mapping custom modification patterns (keys) to UNIMOD IDs (values)
    :raises TypeError: if keys are not strings or values are not integers
    :raises ValueError: if the keys do not start with [A-Z,a-z,^,$]
    :return: A dictionary mapping custom modification patterns (keys) to the ProForma standard (values)
    """
    key_pattern = (
        "'X' or 'X<mod_pattern>' where X is either the one-letter code of an aminoacid or '^' / '$' defining the"
        " n- or c-terminus, respectively, followed by an optional pattern identifying a specific modification."
    )
    unimod_regex_map = {}
    for k, v in mods.items():
        if not isinstance(v, int):
            raise TypeError(f"UNIMOD id {v} for replacement {k} not understood. UNIMOD IDs must be integers.")
        if not isinstance(k, str):
            raise TypeError(
                f"Replacement {k} not understood. Replacements must be strings and follow " f"the pattern {key_pattern}"
            )
        if k[0].isalpha():
            unimod_regex_map[re.escape(k)] = f"{k[0]}[UNIMOD:{v}]"
            continue
        if k[0] == "^":
            unimod_regex_map[f"^{re.escape(k[1:])}"] = f"[UNIMOD:{v}]-"
            continue
        raise ValueError(
            f"Replacement {k} not understood. {k[0]} is not a valid aminoacid. "
            f"Replacements most follow the pattern {key_pattern}"
        )
    return unimod_regex_map


class SearchResults:
    """Handle search results from different software."""

    orig_res: pd.DataFrame
    fake_msms: pd.DataFrame

    def __init__(self, path: Union[str, Path]):
        """
        Init Searchresults object.

        :param path: path to file
        """
        if isinstance(path, str):
            path = Path(path)
        self.path = path

    @abstractmethod
    def read_result(
        self,
        tmt_label: str = "",
        custom_mods: Optional[Dict[str, int]] = None,
    ):
        """Read result.

        :param tmt_label: tmt label as str
        :param custom_mods: dict with custom variable and static identifier and respecitve internal equivalent and mass
        """
        raise NotImplementedError

    def generate_internal(
        self,
        tmt_label: str = "",
        out_path: Optional[Union[str, Path]] = None,
        custom_mods: Optional[Dict[str, int]] = None,
    ) -> pd.DataFrame:
        """
        Generate df and save to out_path if provided.

        :param out_path: path to output
        :param tmt_label: tmt label as str
        :param custom_mods: dict with static and variable custom modifications, their internal identifier and mass
        :return: path to output file
        """
        if out_path is None:
            # convert and return
            return self.read_result(tmt_label, custom_mods=custom_mods)

        if isinstance(out_path, str):
            out_path = Path(out_path)

        if out_path.is_file():
            # only read converted and return
            logger.info(f"Found search results in internal format at {out_path}, skipping conversion")
            # TODO: internal_to_unimod
            return csv.read_file(out_path)

        # convert, save and return
        df = self.read_result(tmt_label, custom_mods=custom_mods)
        csv.write_file(df, out_path)
        return df

    def read_internal(self) -> pd.DataFrame:
        """
        Read file from path.

        :return: dataframe after reading the file
        """
        return csv.read_file(self.path)

    @abstractmethod
    def convert_to_internal(self, mods: Dict[str, str]):
        """
        Convert all columns in the search engine-specific output to the internal format used by Oktoberfest.

        :param mods: dictionary mapping search engine-specific mod patterns (keys) to ProForma standard (values)
        """
        raise NotImplementedError
