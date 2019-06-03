from bombman import Bomb, Flame, Player
import unittest

print "Running Bomb class tests"

class ItemTestCase(unittest.TestCase):
    def setUp(self):
        testPlayer = Player()
        testBomb = Bomb(testPlayer)

    def testDetonator(self):
        """ tests the has_detonator functionality """
        player = Player()
        detoBomb = Bomb(player)
        detoBomb.detonator_time = 5
        detoBomb.time_of_existence = 3

        assert(detoBomb.has_detonator() == True)

    def testExpTime(self):
        """ tests that the code can accurately return the tim until detonation """
        player = Player()
        countBomb = Bomb(player)
        countBomb.detonator_time = 5
        countBomb.explodes_in = 5
        countBomb.time_of_existence = 3

        assert(countBomb.time_until_explosion() == 7)

    def testExplosion(self):
        player = Player()
        shortfuse = Bomb(player)

        shortfuse.explodes()

        assert(shortfuse.has_exploded == True)
