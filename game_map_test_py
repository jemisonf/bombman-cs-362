from bombman import MapTile, GameMap, PlaySetup
import os
import unittest

print "===Running GameMap class tests==="

class GameMapTestCase(unittest.TestCase):
	def setUp(self):
		""" setup, but also tests map creation """
		path = os.path.join('maps','treasure island')
		path2 = os.path.join('maps', 'castle defence')
		fileObj = open(path)
		mapData = fileObj.read()	
		fileObj.close()
		fileObj = open(path2)
		mapData2 = fileObj.read()
		fileObj.close()
		self.gameMap = GameMap(mapData, PlaySetup(), 1, 1)
		self.gameMap2 = GameMap(mapData2, PlaySetup(), 1, 1)

	def testSingleStartingItem(self):
		""" test starting items """
		map = self.gameMap
		items = map.get_starting_items()
		self.assertEquals(items, [3])	#confirms it is the same as the map file: speed boost

	def testMultipleStartingITems(self):
		""" test multiple starting items """
		map = self.gameMap2
		items = map.get_starting_items()
		self.assertEquals(items, [1,1,1,1,7,3])

	def testSpecialTileDetection(self):
		""" test special tile placement: lava """
		map = self.gameMap
		self.assertEqual(map.tile_has_lava((5,3)), True)		
		self.assertEqual(map.tile_has_lava((2,2)), False)	

		
if __name__ == "__main__":
	unittest.main()

	



	

