"""Do not accidentally require Abaqus .sta completion text for CalculiX."""
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch
from ezfea.solver import run_calculix

class SolverTests(unittest.TestCase):
    def test_calculix_success_marker(self):
        with tempfile.TemporaryDirectory() as folder:
            inp=Path(folder)/"analysis.inp"
            inp.write_text("fixture")
            inp.with_suffix(".frd").write_text("solver output")
            inp.with_suffix(".sta").write_text("SUMMARY OF JOB INFORMATION\nSTEP INC ATT\n1 1 1\n")
            with patch("ezfea.solver.shutil.which",return_value="ccx"), \
                 patch("ezfea.solver.subprocess.run",
                       return_value=CompletedProcess(["ccx"],0,"Job finished\n","")):
                output=run_calculix(inp)
            self.assertEqual(output["result_frd"],"analysis.frd")

    def test_incomplete_job_not_counted(self):
        with tempfile.TemporaryDirectory() as folder:
            inp=Path(folder)/"analysis.inp"
            inp.write_text("fixture")
            inp.with_suffix(".frd").write_text("partial")
            with patch("ezfea.solver.shutil.which",return_value="ccx"), \
                 patch("ezfea.solver.subprocess.run",
                       return_value=CompletedProcess(["ccx"],0,"run ended","")):
                with self.assertRaises(RuntimeError):
                    run_calculix(inp)

if __name__=="__main__":
    unittest.main()
