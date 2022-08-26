import io

import pytest
import numpy as np
import pandas as pd

import prosit_io.search_result.maxquant as mq


class TestAddTMTMod:
    def test_add_tmt_mod(self):
        assert mq.MaxQuant.add_tmt_mod(1.0, '[UNIMOD:2016]ABC[UNIMOD:4]K[UNIMOD:2016]', '[UNIMOD:2016]') == 1.0 + 2*304.207146


class TestUpdateColumns:
    def test_update_columns(self, maxquant_df):
        prosit_df = mq.MaxQuant.update_columns_for_prosit(maxquant_df, tmt_labeled='')
        assert prosit_df['REVERSE'][0] == False
        assert prosit_df['REVERSE'][3] == True
        
        assert prosit_df['MODIFIED_SEQUENCE'][0] == 'DS[UNIMOD:21]DS[UNIMOD:21]WDADAFSVEDPVRK'
        assert prosit_df['MODIFIED_SEQUENCE'][3] == 'SS[UNIMOD:21]PTPES[UNIMOD:21]PTMLTK'
        
        assert prosit_df['SEQUENCE'][0] == 'DSDSWDADAFSVEDPVRK'
        assert prosit_df['SEQUENCE'][3] == 'SSPTPESPTMLTK'
        
        assert prosit_df['PEPTIDE_LENGTH'][0] == 18
        assert prosit_df['PEPTIDE_LENGTH'][3] == 13
    
    def test_update_columns_silac(self, maxquant_df):
        maxquant_df['LABELING_STATE'] = [1, 1, 1, 2, 2]
        prosit_df = mq.MaxQuant.update_columns_for_prosit(maxquant_df, tmt_labeled='')
        assert prosit_df['MODIFIED_SEQUENCE'][0] == 'DS[UNIMOD:21]DS[UNIMOD:21]WDADAFSVEDPVR[UNIMOD:267]K[UNIMOD:259]'
        assert prosit_df['MODIFIED_SEQUENCE'][3] == 'SS[UNIMOD:21]PTPES[UNIMOD:21]PTMLTK'

    def test_update_columns_tmt(self, maxquant_df):
        prosit_df = mq.MaxQuant.update_columns_for_prosit(maxquant_df, tmt_labeled='tmt')
        assert prosit_df['MODIFIED_SEQUENCE'][0] == '[UNIMOD:737]DS[UNIMOD:21]DS[UNIMOD:21]WDADAFSVEDPVRK[UNIMOD:737]'
        assert prosit_df['MODIFIED_SEQUENCE'][3] == '[UNIMOD:737]SS[UNIMOD:21]PTPES[UNIMOD:21]PTMLTK[UNIMOD:737]'
    
    def test_update_columns_tmt_msa(self, maxquant_df):
        prosit_df = mq.MaxQuant.update_columns_for_prosit(maxquant_df, tmt_labeled='tmt_msa')
        assert prosit_df['MODIFIED_SEQUENCE_MSA'][0] == '[UNIMOD:737]DS[UNIMOD:23]DS[UNIMOD:23]WDADAFSVEDPVRK[UNIMOD:737]'
        assert prosit_df['MODIFIED_SEQUENCE_MSA'][3] == '[UNIMOD:737]SS[UNIMOD:23]PTPES[UNIMOD:23]PTMLTK[UNIMOD:737]'
    


# Creating dataframes from strings: https://towardsdatascience.com/67b0c2b71e6a
@pytest.fixture
def maxquant_df():
    df_string = """              MODIFIED_SEQUENCE; REVERSE; MASS;
_DS(Phospho (STY))DS(Phospho (STY))WDADAFSVEDPVRK_;        ;  1.0;
_DS(Phospho (STY))DS(Phospho (STY))WDADAFSVEDPVRK_;        ;  1.0;
_DS(Phospho (STY))DSWDADAFS(Phospho (STY))VEDPVRK_;        ;  1.0;
     _SS(Phospho (STY))PTPES(Phospho (STY))PTMLTK_;       +;  2.0;
     _SS(Phospho (STY))PTPES(Phospho (STY))PTMLTK_;       +;  2.0;"""
    df = pd.read_csv(io.StringIO(df_string), delimiter=';', skipinitialspace=True)
    df['Charge'] = 2
    return df
