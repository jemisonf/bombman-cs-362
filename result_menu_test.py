from bombman import Menu, ResultMenu, Player
from stub_sound_player import StubSoundPlayer
import unittest

class ResultMenuTestCase(unittest.TestCase):
    def setUp(self):
        self.sound_player = StubSoundPlayer()
        self.menu = ResultMenu(self.sound_player)

        player_one = Player()
        player_one.team_number = 1
        player_one.number = 1
        self.player_one = player_one

        player_two = Player()
        player_two.team_number = 2
        player_two.number = 2
        self.player_two = player_two

        player_three = Player()
        player_three.team_number = 3
        player_three.number = 3
        self.player_three = player_three

        player_four = Player()
        player_four.team_number = 1
        player_four.number = 4
        self.player_four = player_four

        player_five = Player()
        player_five.team_number = 2
        player_five.number = 5
        self.player_five = player_five

        player_six = Player()
        player_six.team_number = 3
        player_five.number = 6
        self.player_six = player_six

    def testSingleWin(self):
        """ test text output for an individual player """
        menu = self.menu
        # these expected output values are finicky and might need to be tweaked if the test seems like it should be passing
        expected_output = "Winner team is ^#555555black^#FFFFFF!\n" \
                          "__________________________________________________\n" \
                          "^#555555black^#FFFFFF (^#5555552^#FFFFFF): 0/0\n\n" \
                          "__________________________________________________"
        # here we expect a message congradulating a single team and a single player line

        menu.set_results([self.player_one])

        self.assertEqual(menu.text, expected_output)

    def testMultipleWins(self):
        """ test output when multiple teams win """ 
        menu = self.menu
        # these expected output values are finicky and might need to be tweaked if the test seems like it should be passing
        expected_output = "Winners teams are: ^#555555black^#FFFFFF, ^#ff4b4bred^#FFFFFF!\n" \
                          "__________________________________________________\n" \
                          "^#555555black^#FFFFFF (^#5555552^#FFFFFF): 0/0     " \
                          "^#ff4b4bred^#FFFFFF (^#ff4b4b3^#FFFFFF): 0/0\n\n" \
                          "__________________________________________________"
        # here we expected a message congradulating *two* teams and then a line with two columns for two players

        menu.set_results([self.player_one, self.player_two])

        self.assertEqual(menu.text, expected_output)

    def testTwoPlayerTeam(self):
        """ test output when one team with two players wins """
        menu = self.menu
        # these expected output values are finicky and might need to be tweaked if the test seems like it should be passing
        expected_output = "Winner team is ^#555555black^#FFFFFF!\n" \
                          "__________________________________________________\n" \
                          "^#555555black^#FFFFFF (^#5555552^#FFFFFF): 0/1     " \
                          "^#ff4b4bred^#FFFFFF (^#ff4b4b3^#FFFFFF): 0/0     " \
                          "^#4bff4bgreen^#FFFFFF (^#5555552^#FFFFFF): 0/1\n\n" \
                          "__________________________________________________"
        # here we expected three columns below a message congradulating *one* team
        # the two players (1st and 3rd column) should have different player colors but the same team color (in parentheses)
                        
        self.player_one.set_wins(1)
        self.player_four.set_wins(1)

        menu.set_results([self.player_one, self.player_two, self.player_four])
        self.assertEqual(menu.text, expected_output)

    def testPlayerKillWinRatioOutput(self):
        """ test the output for player kills and wins in different combinations """
        """ test output when one team with two players wins """
        menu = self.menu
        # these expected output values are finicky and might need to be tweaked if the test seems like it should be passing
        expected_output = "#555555black^#FFFFFF (^#5555552^#FFFFFF): 1/1     " \
                          "^#ff4b4bred^#FFFFFF (^#ff4b4b3^#FFFFFF): 2/0     " \
                          "^#4bff4bgreen^#FFFFFF (^#5555552^#FFFFFF): 0/2"
                        
        self.player_one.set_wins(1)
        self.player_one.set_kills(1)
        self.player_four.set_wins(2)
        self.player_two.set_kills(2)

        menu.set_results([self.player_one, self.player_two, self.player_four])
        self.assertTrue(expected_output in menu.text)


if __name__ == "__main__":
    unittest.main()
