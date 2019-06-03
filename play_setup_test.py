from bombman import PlaySetup
import unittest

print "===Running PlaySetup class tests==="
class PlaySetupTestCase(unittest.TestCase):
    def setUp(self):
         self.set = PlaySetup()

    def testDefaultSlots(self):
        playSet = self.set
        slots = playSet.get_slots()
        #There are 8 slots, with first being player and next 3 AI by default
        self.assertEqual(slots, [(0,0), (-1,1), (-1,2), (-1,3), None, None, None, None, None, None])

    def testNumberOfGames(self):
        playSet = self.set
        games = playSet.get_number_of_games()
        self.assertEqual(games, 10)

        playSet.increase_number_of_games()
        playSet.increase_number_of_games()
        playSet.increase_number_of_games()
        playSet.decrease_number_of_games()
        games = playSet.get_number_of_games()
        self.assertEqual(games, 12)

    def testNonDefaultSlots(self):
        playSet = self.set
        #shouldn't be allowed to have multiple players under the same player name. 
        #Needs a new method to change them or just refactoring
        playSet.player_slots = [(0,0), (0,0), None, None, None, None, None, None]
        self.assertEqual(playSet.get_slots(), [(0,0), (0,0), None, None, None, None, None, None])
        
if __name__ == "__main__":
	unittest.main()