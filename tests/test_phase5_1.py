import tempfile
from pathlib import Path
import unittest
from vcse.phase5_1 import CapabilityLibrary, _image_verifier, _run, fixture_cases, png_bytes, run_experiment

class WallpaperTests(unittest.TestCase):
    def test_png_verifier(self):
        image=png_bytes()
        self.assertTrue(_image_verifier(image))
        self.assertFalse(_image_verifier(image[:-1]))
        self.assertFalse(_image_verifier(b'not png'))
    def test_direct_browser_download(self):
        self.assertTrue(_run(fixture_cases()[0])['completed'])
    def test_hidden_menu_download(self):
        r=_run(fixture_cases()[1]);self.assertTrue(r['completed']);self.assertEqual([x['element'] for x in r['actions']],['more','save-device'])
    def test_bookmark_is_not_verified_download(self):
        r=_run(fixture_cases()[2]);self.assertTrue(r['completed']);self.assertEqual(r['actions'][-1]['element'],'download-original')
        self.assertTrue(all(not x['verified'] for x in r['actions'][:-1]))
    def test_save_bookmark_does_not_count_as_download(self):
        r=_run(fixture_cases()[2],learned_plan=['#more','#bookmark','#download-original'])
        self.assertTrue(r['completed'])
        self.assertEqual([x['element'] for x in r['actions']],['more','bookmark','download-original'])
        self.assertFalse(r['actions'][1]['download'])
    def test_reject_unverified_skill(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):CapabilityLibrary(Path(d)/'skills.json').save(fixture_cases()[0],{'completed':False})
    def test_transfer_from_other_page(self):
        with tempfile.TemporaryDirectory() as d:
            r=run_experiment(str(Path(d)/'skills.json'),str(Path(d)/'result.json'))
            self.assertEqual(r['verified_first'],3)
            self.assertEqual(r['verified_transfer'],3)
            self.assertTrue(all(x['attempted_cross_site_plan'] for x in r['transfer_pass']))

if __name__=='__main__':unittest.main()
