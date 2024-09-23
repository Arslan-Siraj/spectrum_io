import logging
from pathlib import Path
from typing import Dict, Optional, Tuple, Union

import pandas as pd
import spectrum_fundamentals.constants as c
from pyteomics import pepxml
from spectrum_fundamentals.constants import MSFRAGGER_VAR_MODS
from spectrum_fundamentals.mod_string import internal_without_mods, add_permutations
from tqdm import tqdm

from .search_results import SearchResults, filter_valid_prosit_sequences, parse_mods

logger = logging.getLogger(__name__)


class MSFragger(SearchResults):
    """Handle search results from MSFragger."""

    @property
    def standard_mods(self):
        """Standard modifications that are always applied if not otherwise specified."""
        return {"C": 4, "M[147]": 35}

    def read_result(
        self,
        tmt_label: str = "",
        custom_mods: Optional[Dict[str, int]] = None,
    ) -> pd.DataFrame:
        """
        Function to read a msms txt and perform some basic formatting.

        :param tmt_label: optional tmt label as str
        :param custom_mods: optional dictionary mapping MSFragger-specific mod pattern to UNIMOD IDs.
            If None, static carbamidomethylation of cytein and variable oxidation of methionine
            are mapped automatically. To avoid this, explicitely provide an empty dictionary.
        :raises FileNotFoundError: in case the given path is neither a file, nor a directory.
        :return: pd.DataFrame with the formatted data
        """
        parsed_mods = parse_mods(self.standard_mods | (custom_mods or {}))
        if tmt_label:
            unimod_tag = c.TMT_MODS[tmt_label]
            parsed_mods["K"] = f"K{unimod_tag}"
            parsed_mods[r"^n\[\d+\]"] = f"{unimod_tag}-"
        if self.path.is_file():
            file_list = [self.path]
        elif self.path.is_dir():
            file_list = list(self.path.rglob("*.pepXML"))
        else:
            raise FileNotFoundError(f"{self.path} could not be found.")

        ms_frag_results = []
        for pep_xml_file in tqdm(file_list):
            ms_frag_results.append(pepxml.DataFrame(str(pep_xml_file)))

        self.results = pd.concat(ms_frag_results)

        self.convert_to_internal(mods=parsed_mods)
        return filter_valid_prosit_sequences(self.results)

    def check_decoys(protein_names: str):
        """
        Check if all protein names in a given string correspond to decoy proteins.

        :param protein_names: A string containing one or more protein names separated by semicolons (';').
                            Each protein name is checked for the presence of the substring 'rev'.
        :return: `True` if all proteins are decoy proteins (i.e., if all protein names contain 'rev'),
                otherwise `False`.
        """
        all_proteins = protein_names.split(';')
        reverse= True
        for protein in all_proteins:
            if 'rev' not in protein:
                reverse = False
                break
        return reverse

    def convert_to_internal(self, mods: Dict[str, str],ptm_unimod_id: int,
        ptm_sites: list[str]):
        """
        Convert all columns in the MSFragger output to the internal format used by Oktoberfest.

        :param mods: dictionary mapping MSFragger-specific mod patterns (keys) to ProForma standard (values)
        """
        df = self.results
        df["protein"] = df["protein"].fillna("UNKNOWN").apply(lambda x: ";".join(x))

        df["REVERSE"] = df["protein"].apply(lambda x: check_decoys(x))
        df["spectrum"] = df["spectrum"].str.split(pat=".", n=1).str[0]
        df["PEPTIDE_LENGTH"] = df["peptide"].str.len()

        df.replace({"modified_peptide": mods}, regex=True, inplace=True)
        df["peptide"] = internal_without_mods(df["modified_peptide"])

        if ptm_unimod_id != 0:
            #PTM permutation generation
            if ptm_unimod_id == 7:
                allow_one_less_modification = True
            else:
                allow_one_less_modification = False
            
            df['modified_peptide'] = df['modified_peptide'].apply(add_permutations,unimod_id=ptm_unimod_id, residues=ptm_sites,
                                                                allow_one_less_modification=allow_one_less_modification, axis=1)
            df = df.explode('modified_peptide', ignore_index=True)

        df.rename(
            columns={
                "assumed_charge": "PRECURSOR_CHARGE",
                "index": "SCAN_EVENT_NUMBER",
                "peptide": "SEQUENCE",
                "start_scan": "SCAN_NUMBER",
                "hyperscore": "SCORE",
                "modified_peptide": "MODIFIED_SEQUENCE",
                "protein": "PROTEINS",
                "peptide": "SEQUENCE",
                "precursor_neutral_mass": "MASS",
                "spectrum": "RAW_FILE",
            },
            inplace=True,
        )

        """
        return df[
            [
                "RAW_FILE",
                "SCAN_NUMBER",
                "MODIFIED_SEQUENCE",
                "PRECURSOR_CHARGE",
                "SCAN_EVENT_NUMBER",
                "MASS",
                "SCORE",
                "REVERSE",
                "SEQUENCE",
                "PEPTIDE_LENGTH",
                "PROTEINS",
            ]
        ]
        """
