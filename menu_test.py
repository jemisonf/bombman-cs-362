from bombman import Menu
from stub_sound_player import StubSoundPlayer
import unittest

class MenuTestCase(unittest.TestCase):
    def setUp(self):
        self.sound_player = StubSoundPlayer()
        self.menu = Menu(self.sound_player)
        self.menu.items = [("one", "two")]

    def testLeaving(self):
        """ Test if the leaving function sets the menu_left flag """
        menu = self.menu
        menu.leaving()
        assert menu.menu_left

    def testPromptIfNeeded(self):
        """ Test if the user is prompted when prompt if needed is called """
        menu = self.menu
        menu.state =  Menu.MENU_STATE_CONFIRM
        menu.confirm_prompt_result = None
        self.assertEqual(menu.get_selected_item(), (0,0))
        menu.prompt_if_needed((0,0))
        self.assertEqual(menu.get_state(), Menu.MENU_STATE_CONFIRM_PROMPT)
    
    # TODO this appears to be an actual bug
    def testScrollDown(self):
        """ Test scrolling down from initial state """
        menu = self.menu
        menu.scroll(False) # scroll down
        scroll_pos_down = menu.get_scroll_position()
        self.assertEqual(scroll_pos_down, 1)
    
    def testScrollUp(self):
        """ Test scrolling up from modified state """
        menu = self.menu
        menu.scroll_position = 1
        menu.scroll(True)
        self.assertEqual(menu.get_scroll_position(), 0)
        

if __name__ == "__main__":
    unittest.main()
