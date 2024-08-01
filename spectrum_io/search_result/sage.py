import logging
from pathlib import Path
from typing import Dict, Optional, Tuple, Union

import pandas as pd
import spectrum_fundamentals.constants as c
from spectrum_fundamentals.mod_string import internal_without_mods

from .search_results import SearchResults, filter_valid_prosit_sequences, parse_mods

logger = logging.getLogger(__name__)


class Sage(SearchResults):
    """Handle search results from Sage."""

    def read_result(
        self,
        tmt_label: str = "",
        custom_mods: Optional[Dict[str, int]] = None,
    ) -> pd.DataFrame:
        """
        Function to read a msms tsv and perform some basic formatting.

        :param tmt_label: optional tmt label as str
        :param custom_mods: optional dictionary mapping Sage-specific mod pattern to UNIMOD IDs.
            If None, static carbamidomethylation of cytein and variable oxidation of methionine
            are mapped automatically. To avoid this, explicitely provide an empty dictionary.
        :return: pd.DataFrame with the formatted data
        """
        if custom_mods is None:
            custom_mods = {
                "C[+57.0215]": 4,
                "M[+15.9949]": 35,
                "M[+15.994]": 35,
            }
        parsed_mods = parse_mods(custom_mods)
        if tmt_label:
            unimod_tag = c.TMT_MODS[tmt_label]
            parsed_mods[r"K\[\+\d+\.\d+\]"] = f"K{unimod_tag}"
            parsed_mods[r"^\[\+\d+\.\d+\]"] = f"{unimod_tag}"

        logger.info(f"Reading {self.path}")
        self.results = pd.read_csv(
            self.path,
            usecols=["filename", "scannr", "peptide", "charge", "hyperscore", "calcmass", "label", "proteins"],
            sep="\t",
        )
        logger.info(f"Finished reading {self.path}")

        self.convert_to_internal(mods=parsed_mods)
        print(parsed_mods, self.results)
        return filter_valid_prosit_sequences(self.results)

    def convert_to_internal(self, mods: Dict[str, str]) -> pd.DataFrame:
        """
        Convert all columns in the Sage output to the internal format used by Oktoberfest.

        :param mods: dictionary mapping Sage-specific mod patterns (keys) to ProForma standard (values)
        """
        df = self.results

        # removing .mzML
        df.fillna({"proteins": "UNKNOWN"}, inplace=True)
        df.replace({"filename": {r"\.mz[M|m][l|L]": ""}, "peptide": mods}, regex=True, inplace=True)
        df["scannr"] = df["scannr"].str.rsplit(pat="=", n=1).str[1].astype(int)
        df["label"] = df["label"] < 0
        df["SEQUENCE"] = internal_without_mods(df["peptide"])
        df["PEPTIDE_LENGTH"] = df["SEQUENCE"].str.len()

        df.rename(
            columns={
                "filename": "RAW_FILE",
                "scannr": "SCAN_NUMBER",
                "peptide": "MODIFIED_SEQUENCE",
                "charge": "PRECURSOR_CHARGE",
                "calcmass": "MASS",
                "hyperscore": "SCORE",
                "label": "REVERSE",
                "proteins": "PROTEINS",
            },
            inplace=True,
        )
