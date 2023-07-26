import logging
import re
import pandas as pd
import spectrum_fundamentals.constants as c
from .search_results import SearchResults

#from search_results import SearchResults

logger = logging.getLogger(__name__)

class XlinkX(SearchResults):
    """Handle search results from XlinkX."""

    @staticmethod
    def read_result(path: str, tmt_labeled: str) -> pd.DataFrame:
        """
        Function to read a msms txt of CSMs and perform some basic formatting.

        :param path: path to msms.txt to read
        :return: pd.DataFrame with the formatted data
        """
        logger.info("Reading msms.txt file")
        columns_to_read = ["Sequence",
                        "Crosslinker",
                        "Crosslink Type",
                        "XlinkX Score",
                        "Charge",
                        "MH+ [Da]",
                        "First Scan",
                        "RT [min]",
                        "Is Decoy",
                        "Accessions",
                        "Sequence A",
                        "Modifications A",
                        "Crosslinker Position A",
                        "Protein Accession A",
                        "Sequence B",
                        "Modifications B",
                        "Crosslinker Position B",
                        "Protein Accession A",
                        "Spectrum File"] 
        df = pd.read_csv(path, usecols=columns_to_read, sep='\t')
        logger.info("Finished reading msms.txt file")

        # Standardize column names
        df = XlinkX.update_columns_for_prosit(df)
        df = XlinkX.filter_valid_prosit_sequences(df)
        return df

    def add_mod_sequence(seq_a: str,
                         seq_b: str,
                         mod_a: str,
                         mod_b: str,
                         crosslinker_position_a: int,
                         crosslinker_position_b: int):
        """
        Function adds modification in peptide sequence for xl-prosit 
        
        :seq_a: unmodified peptide a
        :seq_b: unmodified peptide b
        :mod_a: all modifications of pep a
        :mod_b: all modifications of pep b
        :crosslinker_position_a: crosslinker position of peptide a
        :crosslinker_position_b: crosslinker position of peptide b
        :crosslinker_type: crosslinker tpe eg. DSSO, DSBU
        :return: modified sequence a and b
        """
        split_seq_a = [x for x in seq_a]
        split_seq_b = [x for x in seq_b]

        for mod_a in mod_a.split(";"):
            if re.search(r'\((.*?)\)', mod_a).group(1) == "Oxidation":
                modification = "M[UNIMOD:35]"
                pos_mod_a = int(re.findall(r'\d+', mod_a)[0])
                split_seq_a[pos_mod_a-1] = modification
            elif re.search(r'\((.*?)\)', mod_a).group(1) == "Carbamidomethyl":
                modification = "C[UNIMOD:4]"
                pos_mod_a = int(re.findall(r'\d+', mod_a)[0])
                split_seq_a[pos_mod_a-1] = modification
            elif re.search(r'\((.*?)\)', mod_a).group(1) == "DSSO":
                modification = "K[UNIMOD:1896]"
                split_seq_a[crosslinker_position_a-1] = modification
            elif mod in ["nan", "null"]:
                break
            else:
                raise AssertionError(f"unknown modification provided:{mod}")

        for mod_b in mod_b.split(";"):
            if re.search(r'\((.*?)\)', mod_b).group(1) == "Oxidation":
                modification = "M[UNIMOD:35]"
                pos_mod_b = int(re.findall(r'\d+', mod_b)[0])
                split_seq_b[pos_mod_b-1] = modification
            elif re.search(r'\((.*?)\)', mod_b).group(1) == "Carbamidomethyl":
                modification = "C[UNIMOD:4]"
                pos_mod_b = int(re.findall(r'\d+', mod_b)[0])
                split_seq_b[pos_mod_b-1] = modification
            elif re.search(r'\((.*?)\)', mod_b).group(1) == "DSSO":
                modification = "K[UNIMOD:1896]"
                split_seq_b[crosslinker_position_b-1] = modification
            elif mod in ["nan", "null"]:
                break
            else:
                raise AssertionError(f"unknown modification provided:{mod}")
        
        seq_mod_a = ''.join(split_seq_a)    
        seq_mod_b = ''.join(split_seq_b)      

        return seq_mod_a, seq_mod_b


    @staticmethod
    def update_columns_for_prosit(df: pd.DataFrame) -> pd.DataFrame:
        """
        Update columns of df to work with Prosit.

        :param df: df to modify
        :return: modified df as pd.DataFrame
        """
        df.rename(columns={"Spectrum File": "RAW_FILE", 
                           "MH+ [Da]": "MASS", #Experimental Mass of crosslinked peptides
                           "Charge": "PRECURSOR_CHARGE",
                           "Crosslinker": "CROSSLINKER_TYPE",
                           "XlinkX Score":"SCORE",
                           "Is Decoy": "REVERSE",
                           "First Scan": "SCAN_NUMBER",
                           "Spectrum File": "RAW_FILE",
                           "Sequence A": "SEQUENCE_A",
                           "Sequence B": "SEQUENCE_B",
                           "Modifications A": "Modifications_A",
                           "Modifications B": "Modifications_B",
                           "Crosslinker Position A": "CROSSLINKER_POSITION_A",
                           "Crosslinker Position B": "CROSSLINKER_POSITION_B"},
                             inplace=True)
        
        logger.info("Converting XlinkX peptide sequence to internal format")

        df["PEPTIDE_LENGTH_A"] = df['SEQUENCE_A'].apply(len) 
        df["PEPTIDE_LENGTH_B"] = df['SEQUENCE_B'].apply(len)

        df["RAW_FILE"] = df['RAW_FILE'].str.replace(".raw","")

        df['Modifications_A'] = df['Modifications_A'].astype('str') 
        df['Modifications_B'] = df['Modifications_B'].astype('str')
        
        df['CROSSLINKER_POSITION_A'] = df['CROSSLINKER_POSITION_A'].astype('int')
        df['CROSSLINKER_POSITION_B'] = df['CROSSLINKER_POSITION_B'].astype('int')
        
          
        df[['MODIFIED_SEQUENCE_A','MODIFIED_SEQUENCE_B']] = df.apply(lambda row: XlinkX.add_mod_sequence(row['SEQUENCE_A'], 
                                                                                 row['SEQUENCE_B'],
                                                                                 row['Modifications_A'],
                                                                                 row['Modifications_B'],
                                                                                 row['CROSSLINKER_POSITION_A'],
                                                                                 row['CROSSLINKER_POSITION_B']), axis=1, result_type='expand')
        
        return df

    @staticmethod
    def filter_valid_prosit_sequences(df: pd.DataFrame) -> pd.DataFrame:
        """
        Filter valid Prosit sequences.

        :param df: df to filter
        :return: df after filtration
        """
        logger.info(f"#sequences before filtering for valid prosit sequences: {len(df.index)}")

        df = df[(df["PEPTIDE_LENGTH_A"] <= 30)]
        df = df[df["PEPTIDE_LENGTH_A"] >= 6]
        df = df[(df["PEPTIDE_LENGTH_B"] <= 30)]
        df = df[df["PEPTIDE_LENGTH_B"] >= 6]
        df = df[(~df["SEQUENCE_A"].str.contains("U"))]
        df = df[(~df["SEQUENCE_B"].str.contains("U"))]
        df = df[df["PRECURSOR_CHARGE"] <= 6]
        logger.info(f"#sequences after filtering for valid prosit sequences: {len(df.index)}")

        return df





