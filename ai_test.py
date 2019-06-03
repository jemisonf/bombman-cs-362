from bombman import *
import random
import unittest

class AITestCase(unittest.TestCase):
    def setUp(self):
        self.test_play_setup = PlaySetup()
        self.test_play_setup.set_number_of_games(1)
        mapfile = open(os.path.join(Game.MAP_PATH,"classic"))
        map_data = mapfile.read()
        mapfile.close
        self.test_map = GameMap(map_data,self.test_play_setup,0,0)
        self.aiPlayer = self.test_map.get_players()[0]
        self.testPlayer = self.test_map.get_players()[1]
        self.testAI = AI(self.test_map.get_players()[0],self.test_map)

    def testEscape(self):        
        assert(not self.testAI.tile_is_escapable((-2,-2)))#Out of bounds should not be escapable
        tmp = self.test_map.get_tile_at((5,5))
        tmp.flames
        assert(not self.testAI.tile_is_escapable((5,5)))# Set a tile on fire and it should not be tile_is_escapable
        tmp = self.test_map.get_tile_at((6,6))
        tmp.special_object = MapTile.SPECIAL_OBJECT_LAVA
        assert(not self.testAI.tile_is_escapable((6,6)))# Test a lava tile
        tmp = self.test_map.get_tile_at((0,0))
        assert(self.testAI.tile_is_escapable((0,0)))# Test a normal spot

    def testDecideDir(self):# Check that the ai never decides to walk out of bounds
        for y in xrange(0,self.test_map.MAP_WIDTH):#Test all locations on the board
            for x in xrange(0,self.test_map.MAP_HEIGHT):
                self.aiPlayer.set_position((x,y))
                tmp = self.testAI.decide_general_direction()
                tmp = (x+tmp[0],y+tmp[1])
                assert(tmp[0] >= 0 and tmp[0] <= self.test_map.MAP_HEIGHT)
                assert(tmp[1] >= 0 and tmp[1] <= self.test_map.MAP_WIDTH)
        
        #Test avoidence
        # Trap the AI so it only has one way to go and check that it's reacing to the location of players
        # Diagram: CL = clear PL = player
        # First choice: Move up
        # [CL] [CL] 
        # [AI] [PL]
        #
        #Second choice: move right
        # [PL] [CL] 
        # [AI] [CL]
        self.aiPlayer.set_position((0,0))
        self.testPlayer.set_position((0,1))
        tmp = self.testAI.decide_general_direction()
        self.testPlayer.set_position((1,0))        
        assert(self.testAI.decide_general_direction() != tmp)# make sure that it's reacting to players

    def testTrapped(self):
        assert(not self.testAI.is_trapped())# The ai is not initaly traped
        self.aiPlayer.set_position((-1,-1))
        assert(self.testAI.is_trapped())# Ai is out of bounds and has no where to go
        self.aiPlayer.set_position((-1,0))
        assert(not self.testAI.is_trapped())#Ai can move in bounds
    
    def testNearbyPlayers(self):
        assert(self.testAI.players_nearby() == (0,0))# Ai starts alone
        self.testPlayer.set_position((0,1))
        self.aiPlayer.set_position((0,0))
        assert(self.testAI.players_nearby() == (1,0))# Place enemy
        self.testPlayer.set_team_number(1)
        self.aiPlayer.set_team_number(1)
        assert(self.testAI.players_nearby() == (0,1))# Test allies
        self.test_map.get_players()[3].set_position((1,1))
        assert(self.testAI.players_nearby() == (1,1))# Diagnal
        






if __name__ == "__main__":
    unittest.main()
