from sqlite3 import Connection
from typing import IO, Dict, Union, Tuple, Optional

import numpy as np
import pandas as pd
from spectrum_fundamentals.constants import PARTICLE_MASSES
from spectrum_fundamentals.mod_string import internal_to_mod_names, internal_without_mods

from .spectral_library import SpectralLibrary


class MSP(SpectralLibrary):
    """Main to initialze a MSP obj."""

    @staticmethod
    def _assemble_fragment_string(f_mz: float, f_int: float, f_a: bytes):
        annot = f_a[:-2].decode() if f_a.endswith(b"1") else f_a.replace(b"+", b"^").decode()
        return f'{f_mz:.8f}\t{f_int:.4f}\t"{annot}/0.0ppm"\n'

    def _write(self, out: Union[IO, Connection], data: Dict[str, np.ndarray], metadata: pd.DataFrame, 
               custom_mods: Optional[Dict[str, Dict[str, Tuple[str, float]]]] = None):
        # prepare metadata
        if isinstance(out, Connection):
            raise TypeError("Not supported. Use DLib if you want to write a database file.")
        stripped_peptides = metadata["SEQUENCE"]
        modss = internal_to_mod_names(metadata["MODIFIED_SEQUENCE"])
        p_charges = metadata["PRECURSOR_CHARGE"]
        p_mzs = (metadata["MASS"] + (p_charges * PARTICLE_MASSES["PROTON"])) / p_charges
        ces = metadata["COLLISION_ENERGY"]
        pr_ids = metadata["PROTEINS"]

        # prepare spectra
        irts = data["irt"][:, 0]  # should create a 1D view of the (n_peptides, 1) shaped array
        f_mzss = data["mz"]
        f_intss = data["intensities"]
        f_annotss = data["annotation"]

        lines = []
        vec_assemble = np.vectorize(MSP._assemble_fragment_string)

        for stripped_peptide, p_charge, p_mz, ce, pr_id, mods, irt, f_mzs, f_ints, f_annots in zip(
            stripped_peptides, p_charges, p_mzs, ces, pr_ids, modss, irts, f_mzss, f_intss, f_annotss
        ):
            lines.append(f"Name: {stripped_peptide}/{p_charge}\nMW: {p_mz}\n")
            lines.append(
                f"Comment: Parent={p_mz:.8f} Collision_energy={ce} Protein_ids={pr_id} Mods={mods[0]} "
                f"ModString={mods[1]}/{p_charge} iRT={irt:.2f}\n"
            )

            cond = self._fragment_filter_passed(f_mzs, f_ints)
            fragment_list = vec_assemble(f_mzs[cond], f_ints[cond], f_annots[cond])

            lines.append(f"Num peaks: {len(fragment_list)}\n")

            lines.extend(fragment_list)
        out.writelines(lines)

    def _initialize(self, out: Union[IO, Connection]):
        pass
