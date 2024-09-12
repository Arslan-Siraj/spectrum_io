import logging
from typing import Dict, Optional

import pandas as pd
from spectrum_fundamentals.constants import PARTICLE_MASSES

from .search_results import SearchResults, filter_valid_prosit_sequences, parse_mods

logger = logging.getLogger(__name__)


class MSAmanda(SearchResults):
    """Handle search results from MSAmanda."""

    @property
    def standard_mods(self):
        """Standard modifications that are always applied if not otherwise specified."""
        return {"m": 35, "c": 4}

    def read_result(
        self, tmt_label: str = "", custom_mods: Optional[Dict[str, int]] = None, suffix: str = "output.csv"
    ) -> pd.DataFrame:
        """
        Function to read a msms txt and perform some basic formatting.

        :param tmt_label: optional tmt label as str
        :param custom_mods: optional dictionary mapping Sage-specific mod pattern to UNIMOD IDs.
            If None, static carbamidomethylation of cytein and variable oxidation of methionine
            are mapped automatically. To avoid this, explicitely provide an empty dictionary.
        :param suffix: Optional suffix to determine which fileresult files should be taken from the supplied path
        :raises FileNotFoundError: If the supplied path is not found
        :raises AssertionError: If the supplied path does not contain any files matching the provided suffix.
        :raises NotImplementedError: If tmt label was supplied.
        :return: pd.DataFrame with the formatted data
        """
        parsed_mods = parse_mods(self.standard_mods | (custom_mods or {}))
        print(parsed_mods)
        if tmt_label:
            raise NotImplementedError("TMT is not supported for MSAmanda. Please open an issue on github.")

        if self.path.is_file():
            pathlist = [self.path]
            print("hooray")
        elif self.path.is_dir():
            pathlist = list(self.path.glob(f"*{suffix}"))
            if not pathlist:
                raise AssertionError(f"The directory does not contain any files that match the pattern *{suffix}")
        else:
            raise FileNotFoundError(f"{self.path} does not exist.")

        df_list = []
        for output_file in pathlist:
            logger.info(f"Reading {output_file}...")
            df_list.append(
                pd.read_csv(
                    output_file,
                    sep="\t",
                    skiprows=1,
                    usecols=[
                        "Scan Number",
                        "Sequence",
                        # "Modifications",
                        "Protein Accessions",
                        "Amanda Score",
                        "m/z",
                        "Charge",
                        "Filename",
                    ],
                )
            )
            logger.info(f"Finished reading {output_file}")

        self.results = pd.concat(df_list)

        self.convert_to_internal(mods=parsed_mods)
        return filter_valid_prosit_sequences(self.results)

    def convert_to_internal(self, mods: Dict[str, str]):
        """
        Convert all columns in the Sage output to the internal format used by Oktoberfest.

        :param mods: dictionary mapping Sage-specific mod patterns (keys) to ProForma standard (values)
        """
        df = self.results
        df["REVERSE"] = df["Protein Accessions"].str.startswith("REV_")
        df["m/z"] = df["Charge"] * (df["m/z"] - PARTICLE_MASSES["PROTON"])
        df["SEQUENCE"] = df["Sequence"].str.upper()
        df.replace({"RAW_FILE": {r"\.\w+$": ""}, "Sequence": mods}, regex=True, inplace=True)
        df["PEPTIDE_LENGTH"] = df["SEQUENCE"].str.len()

        df.rename(
            columns={
                "Filename": "RAW_FILE",
                "Scan Number": "SCAN_NUMBER",
                "Sequence": "MODIFIED_SEQUENCE",
                "Charge": "PRECURSOR_CHARGE",
                "m/z": "MASS",
                "Amanda Score": "SCORE",
                "Protein Accessions": "PROTEINS",
            },
            inplace=True,
        )
