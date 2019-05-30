from bombman import Menu, SoundPlayer
from stub_sound_player import StubSoundPlayer
import unittest

class MenuTestCase(unittest.TestCase):
    def setUp(self):
        print "setting up"
        self.sound_player = StubSoundPlayer()
        self.menu = Menu(self.sound_player)

    def testFakeTest(self):
        """ A fake test that will always succeed """
        assert(1 == 1)
