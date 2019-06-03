from bombman import *
import random
import unittest

class PositionableTestCase(unittest.TestCase):
    def setUp(self):

        #Basic testing
        self.objects = []
        for i in xrange(0,5):
            self.objects.append(Positionable())

        #Advanced
        self.test_play_setup = PlaySetup()
        self.test_play_setup.set_number_of_games(1)
        mapfile = open(os.path.join(Game.MAP_PATH,"classic"))
        map_data = mapfile.read()
        mapfile.close
        self.test_map = GameMap(map_data,self.test_play_setup,0,0)

    def testInit(self):
        for i in xrange(0,5):
            assert(self.objects[i].get_position() == (0.0,0.0))
    
    def testSetnGet(self):
        for k in xrange(0,1000):#Do a 1000 tests
            cords = []
            for i in xrange(0,5):#gen 5 random cords for each obj
                cords.append((random.uniform(0,15),random.uniform(0,11)))
                self.objects[i].set_position(cords[i])
                assert(self.objects[i].get_position() == cords[i])
    
    def testNeighbour(self):# Note neighbou can be outside the board
        testPlayer = self.test_map.get_players()[0]
        for y in xrange(0,15):#Test all locations on the board
            for x in xrange(0,11):
                testPlayer.set_position((x,y))
                tmp = testPlayer.get_neighbour_tile_coordinates()
                assert(tmp[0] == (x,y-1))# Left
                assert(tmp[1] == (x+1,y))# Up
                assert(tmp[2] == (x,y+1))# Right
                assert(tmp[3] == (x-1,y))# Down
        
    
    def testTilePosition(self):
        testPlayer = self.test_map.get_players()[0]
        assert(testPlayer.get_tile_position() == (int(math.floor(testPlayer.get_position()[0])),int(math.floor(testPlayer.get_position()[0]))))

    def testTileCenter(self):
        testPlayer = self.test_map.get_players()[0]
        assert(testPlayer.is_near_tile_center())# Centered by default
        testPlayer.set_position((5,5))# Moveing position does not place at center
        assert(not testPlayer.is_near_tile_center())


if __name__ == "__main__":
    unittest.main()
