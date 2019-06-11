from playerClass import Player, Positionable
import unittest

print "Running Player class tests"

class PlayerTestCase(unittest.TestCase):
    def setUp(self):
        testPlayer = Player()

    def testNumber(self):
        """ tests to see if a player's number is correctly updated """
        numTestP = Player()
        numTestP.number = 0
        assert(numTestP.number == 0), "player number was not correctly set!"

    def testKillCount(self):
        """ tests to see if set_kills and get_kills is correctly updated """
        killTestP = Player()
        killTestP.set_kills(3)
        assert(killTestP.get_kills() == 3), "player kills not successfully updated"

    def testWinCount(self):
        """ tests to see if set_wins and get_wins is correctly updated """
        winTestP = Player()
        winTestP.set_wins(7)
        assert(winTestP.get_wins() == 7), "Player wins not successfully updated"

    def testWalk(self):
        """ tests to see if walking is correctly updated """
        walker = Player()
        walker.state = 4 # walking upwards
        assert(walker.is_walking() == True)
        walker.state = 5  # walking right
        assert(walker.is_walking() == True)
        walker.state = 6  # walking downwards
        assert(walker.is_walking() == True)
        walker.state = 7  # walking left
        assert(walker.is_walking() == True)

        # what if we are idle

        walker.state = 2 # idle down state
        assert(walker.is_walking() == False)

    def testEnemyDetection(self):
        """ tests to see if the function is_enemy correctly checks this """
        guineaPig = Player()
        testCaseP = Player()

        guineaPig.team_number = 1
        testCaseP.team_number = 2

        assert(guineaPig.is_enemy(testCaseP) == True)

        guineaPig.team_number = 2
        assert(guineaPig.is_enemy(testCaseP) != True)

    def testDeath(self):
        """ tests to see if death is properly reported by is_dead """
        redshirt = Player()
        redshirt.state = 10 # the state for the player being
        assert(redshirt.is_dead() == True)
