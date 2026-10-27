"""Exercise the actual native Tk window with real solver and no fake results.

Run with an available GUI display and EZFEA_DESKTOP_GUI=1. Linux CI uses
xvfb-run; this test invokes the normal App.demo() and App.run() controls.
"""
import os
import tempfile
import time
from pathlib import Path
import unittest
from unittest.mock import patch

@unittest.skipUnless(os.environ.get("EZFEA_DESKTOP_GUI")=="1",
                     "Native Tk display and CalculiX required")
class DesktopEndToEndTests(unittest.TestCase):
    @patch("app.messagebox.showerror")
    @patch("app.messagebox.askyesno",return_value=False)
    def test_real_drilled_plate_auto_held_plane_can_be_removed(self, confirmation,show_error):
        from app import App
        from ezfea.fixture_examples import drilled_plate_step
        with tempfile.TemporaryDirectory() as folder:
            plate=drilled_plate_step(Path(folder)/"two_bolt_holes.step")
            app=None
            try:
                app=App()
                app.update()
                self.assertTrue(app.load_file(str(plate)))
                until=time.monotonic()+30
                while not app.picker.triangles and time.monotonic()<until:
                    app.update()
                    time.sleep(.06)
                self.assertTrue(app.picker.triangles,app.picker.info.get())
                self.assertEqual(len(app.support_faces),1)
                guess=app.support_faces[0]
                self.assertIn(guess,app.suggested_support_faces)
                self.assertTrue(app.suggestions_review_pending)
                self.assertIn(guess,{f.tag for f in app.faces})
                self.assertEqual(app.picker.support_tags,[guess])
                # Automatic inference does not invent the actual force face.
                self.assertEqual(app.load_box.current(),-1)
                # Remove a suggested support with a single click gesture.
                self.assertTrue(app._on_face_click("fixed",guess))
                self.assertFalse(app.support_faces)
                self.assertFalse(app.suggestions_review_pending)
                # Add it back as a deliberate operator selection.
                self.assertTrue(app._on_face_click("fixed",guess))
                self.assertEqual(app.support_faces,[guess])
                self.assertFalse(app.suggestions_review_pending)
                self.assertEqual(app.picker.fixed_tag,guess)
                show_error.assert_not_called()
                confirmation.assert_not_called()
            finally:
                if app is not None:app.destroy()

    @patch("app.messagebox.showerror")
    def test_demo_buttons_start_actual_native_solve_and_show_numerical_results(self, error_dialog):
        from app import App
        with tempfile.TemporaryDirectory() as temp:
            old=os.getcwd()
            os.chdir(temp)
            app=None
            try:
                app=App()
                app.update_idletasks()
                app.demo()
                self.assertTrue(app.filename.endswith(".step"))
                self.assertGreaterEqual(len(app.faces),6)
                self.assertNotEqual(app.fix_box.current(),app.load_box.current())
                self.assertEqual(app.element_type.get(),"C3D10")
                # The 3D display is actual tessellated OCC surface data, not
                # an invented rectangle. Wait for its separate Gmsh worker.
                preview_timeout=time.monotonic()+65
                while not app.picker.triangles and time.monotonic()<preview_timeout:
                    app.update()
                    time.sleep(.1)
                self.assertTrue(app.picker.triangles,
                    f"Native CAD preview failed: {app.picker.info.get()}")
                self.assertEqual({tag for tag,_ in app.picker.triangles},
                                 {f.tag for f in app.faces})
                app.picker.choose("fixed")
                app.update()
                # Exercise an actual on-screen click (pick a frontmost face
                # whose centroid is not hidden by another surface patch).
                from types import SimpleNamespace
                from ezfea.desktop_preview import face_under_cursor
                visible=None
                original_fixed=app.fix_box.current()
                original_loaded=app.load_box.current()
                for _,tag,tri in reversed(app.picker.painted):
                    if tag in {app.faces[original_loaded].tag,app.faces[original_fixed].tag}:
                        continue
                    px=sum(v[0] for v in tri)/3
                    py=sum(v[1] for v in tri)/3
                    if face_under_cursor(app.picker.painted,px,py)==tag:
                        visible=(tag,px,py)
                        break
                self.assertIsNotNone(visible,
                    "There must be a directly clickable original CAD face other than the loaded face")
                tag,px,py=visible
                evt=SimpleNamespace(x=px,y=py)
                app.picker._down(evt)
                app.picker._up(evt)
                self.assertIn(tag,app.support_faces)
                self.assertIn(tag,app.picker.support_tags)
                self.assertEqual(len(app.support_faces),2)
                # Removing a support point is just clicking it again.
                app.picker._down(evt)
                app.picker._up(evt)
                self.assertNotIn(tag,app.support_faces)
                self.assertEqual(len(app.support_faces),1)
                # Restore demo fixture for independent mechanical verification.
                app.support_faces=[app.faces[original_fixed].tag]
                app.load_box.current(original_loaded)
                app._sync_faces()
                app.run()
                self.assertTrue(app.busy,"RUN control did not actually start")
                end=time.monotonic()+150
                while app.busy and time.monotonic()<end:
                    app.update()
                    time.sleep(.1)
                app.update()
                self.assertFalse(app.busy,"Real native solve timed out")
                self.assertIsNotNone(app.latest,
                    f"No actual solver measurements reached the UI; status={app.status.get()}; error={error_dialog.call_args}")
                error_dialog.assert_not_called()
                self.assertEqual(app.latest["summary"]["status"],"completed")
                self.assertIn("MPa",app.result_vars["max_stress"].get())
                self.assertIn("mm",app.result_vars["max_displacement"].get())
                self.assertIn("PASS",app.result_vars["force_balance"].get())
                self.assertIn("PASS",app.result_vars["moment_balance"].get())
                self.assertTrue(Path(app.latest["folder"],"analysis.frd").is_file())
                self.assertTrue(app.latest["report"].is_file())
                self.assertEqual(str(app.folder_button.cget("state")),"normal")
            finally:
                if app is not None:
                    app.destroy()
                os.chdir(old)


if __name__=="__main__":
    unittest.main()
