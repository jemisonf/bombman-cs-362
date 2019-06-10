#!/usr/bin/env python
# coding=utf-8
#
# Bombman - free and open-source Bomberman clone
#
# Copyright (C) 2016 Miloslav Číž
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# ========================== A FEW COMMENTS ===========================
#
# Version numbering system:
#
# major.minor
#
# Major number increases with significant new features added (multiplayer, ...),
# minor number increases with small changes (bug fixes, AI improvements, ...) and
# it does so in this way: 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 91, 92, 93, etc.
#
# ---------------------------------------------------------------------
#
# Map string format (may contain spaces and newlines, which will be ignored):
#
# <environment>;<player items>;<map items>;<tiles>
#    
# <environment>   - Name of the environment of the map (affects only visual appearance).
# <player items>  - Items that players have from the start of the game (can be an empty string),
#                   each item is represented by one letter (the same letter can appear multiple times):
#                     f - flame
#                     F - superflame
#                     b - bomb
#                     k - kicking shoe
#                     s - speedup
#                     p - spring
#                     d - disease
#                     m - multibomb
#                     r - random
#                     x - boxing glove
#                     e - detonator
#                     t - throwing glove
# <map items>     - Set of items that will be hidden in block on the map. This is a string of the
#                   same format as in <player items>. If there is more items specified than there is
#                   block tiles, then some items will be left out.
# <tiles>         - Left to right, top to bottom sequenced array of map tiles:
#                     . - floor
#                     x - block (destroyable)
#                     # - wall (undestroyable)
#                     A - teleport A
#                     B - teleport B
#                     T - trampoline
#                     V - lava
#                     u - arrow up, floor tile
#                     r - arrow right, floor tile
#                     d - arrow down, floor tile
#                     l - arrow left, floor tile
#                     U - arrow up, under block tile
#                     R - arrow right, under block tile
#                     D - arrow down, under block tile
#                     L - arrow left, under block tile
#                     <0-9> - starting position of the player specified by the number

import sys
import pygame
import os
import math
import copy
import random
import re
import time

from collections import defaultdict

from playerClass import *

DEBUG_PROFILING = False
DEBUG_FPS = False
DEBUG_VERBOSE = False

#------------------------------------------------------------------------------

def debug_log(message):
  if DEBUG_VERBOSE:      
    print(message)

#==============================================================================

class Profiler(object):
  SHOW_LAST = 10

  #----------------------------------------------------------------------------

  def __init__(self):
    self.sections = {}
    
  #----------------------------------------------------------------------------

  def measure_start(self, section_name):
    if not DEBUG_PROFILING:
      return
      
    if not (section_name in self.sections):
      self.sections[section_name] = [0.0 for i in xrange(Profiler.SHOW_LAST)]

    section_values = self.sections[section_name]
        
    section_values[0] -= pygame.time.get_ticks()

  #----------------------------------------------------------------------------

  def measure_stop(self, section_name):
    if not DEBUG_PROFILING:
      return
      
    if not section_name in self.sections:
      return
  
    section_values = self.sections[section_name]
    
    section_values[0] += pygame.time.get_ticks()

  #----------------------------------------------------------------------------
     
  def end_of_frame(self):
    for section_name in self.sections:
      section_values = self.sections[section_name]
      section_values.pop()
      section_values.insert(0,0)

  #----------------------------------------------------------------------------
    
  def get_profile_string(self):
    result = "PROFILING INFO:"
    
    section_names = list(self.sections.keys())
    section_names.sort()
    
    for section_name in section_names:
      result += "\n" + section_name.ljust(25) + ": "
      
      section_values = self.sections[section_name]
      
      for i in xrange(len(section_values)):
        result += str(section_values[i]).ljust(5)
        
      result += " AVG: " + str(sum(section_values) / float(len(section_values)))
        
    return result

#==============================================================================

## Something that has a float position on the map.

class Positionable(object):

  #----------------------------------------------------------------------------

  def __init__(self):
    self.position = (0.0,0.0)

  #----------------------------------------------------------------------------

  def set_position(self,position):
    self.position = position

  #----------------------------------------------------------------------------

  def get_position(self):
    return self.position

  #----------------------------------------------------------------------------
  
  def get_neighbour_tile_coordinates(self):
    tile_coordinates = self.get_tile_position()
    
    top = (tile_coordinates[0],tile_coordinates[1] - 1)
    right = (tile_coordinates[0] + 1,tile_coordinates[1])
    down = (tile_coordinates[0],tile_coordinates[1] + 1)
    left = (tile_coordinates[0] - 1,tile_coordinates[1])  
    
    return (top,right,down,left)

  #----------------------------------------------------------------------------
  
  def get_tile_position(self):
    return Positionable.position_to_tile(self.position)

  #----------------------------------------------------------------------------
  
  ## Moves the object to center of tile (if not specified, objects current tile is used).
  
  def move_to_tile_center(self, tile_coordinates=None):
    if tile_coordinates != None:
      self.position = tile_coordinates
    
    self.position = (math.floor(self.position[0]) + 0.5,math.floor(self.position[1]) + 0.5)

  #----------------------------------------------------------------------------

  ## Converts float position to integer tile position.

  @staticmethod
  def position_to_tile(position):
    return (int(math.floor(position[0])),int(math.floor(position[1])))

  #----------------------------------------------------------------------------
  
  def is_near_tile_center(self):
    position_within_tile = (self.position[0] % 1,self.position[1] % 1)
    
    limit = 0.2
    limit2 = 1.0 - limit
    
    return (limit < position_within_tile[0] < limit2) and (limit < position_within_tile[1] < limit2)

#==============================================================================

## Info about a bomb's flight (when boxed or thrown).

class BombFlightInfo(object):

  #----------------------------------------------------------------------------

  def __init__(self):
    self.total_distance_to_travel = 0     ##< in tiles
    self.distance_travelled = 0           ##< in tiles
    self.direction = (0,0)                ##< in which direction the bomb is flying, 0, 1 or -1

#==============================================================================

class Bomb(Positionable):
  ROLLING_SPEED = 4
  FLYING_SPEED = 5
  
  BOMB_ROLLING_UP = 0
  BOMB_ROLLING_RIGHT = 1
  BOMB_ROLLING_DOWN = 2
  BOMB_ROLLING_LEFT = 3
  BOMB_FLYING = 4
  BOMB_NO_MOVEMENT = 5
  
  DETONATOR_EXPIRATION_TIME = 20000

  BOMB_EXPLODES_IN = 3000
  EXPLODES_IN_QUICK = 800     ##< for when the player has quick explosion disease

  #----------------------------------------------------------------------------
  
  def __init__(self, player):
    super(Bomb,self).__init__()
    self.time_of_existence = 0                       ##< for how long (in ms) the bomb has existed
    self.flame_length = player.get_flame_length()    ##< how far the flame will go
    self.player = player                             ##< to which player the bomb belongs
    self.explodes_in = Bomb.BOMB_EXPLODES_IN         ##< time in ms in which the bomb explodes from the time it was created (detonator_time must expire before this starts counting down)
    self.detonator_time = 0                          ##< if > 0, the bomb has a detonator on it, after expiring it becomes a regular bomb
    self.set_position(player.get_position())
    self.move_to_tile_center()
    self.has_spring = player.bombs_have_spring()
    self.movement = Bomb.BOMB_NO_MOVEMENT
    self.has_exploded = False
    self.flight_info = BombFlightInfo()

  #----------------------------------------------------------------------------
      
  ## Sends the bomb flying from its currents position to given tile (can be outside the map boundaries, will fly over the border from the other side).
    
  def send_flying(self, destination_tile_coords):
    self.movement = Bomb.BOMB_FLYING

    current_tile = self.get_tile_position()
    self.flight_info.distance_travelled = 0

    axis = 1 if current_tile[0] == destination_tile_coords[0] else 0

    self.flight_info.total_distance_to_travel = abs(current_tile[axis] - destination_tile_coords[axis])
    self.flight_info.direction = [0,0]
    self.flight_info.direction[axis] = -1 if current_tile[axis] > destination_tile_coords[axis] else 1
    self.flight_info.direction = tuple(self.flight_info.direction)

    destination_tile_coords = (destination_tile_coords[0] % GameMap.MAP_WIDTH,destination_tile_coords[1] % GameMap.MAP_HEIGHT)
    self.move_to_tile_center(destination_tile_coords)

  #----------------------------------------------------------------------------

  def has_detonator(self):
    return self.detonator_time > 0 and self.time_of_existence < Bomb.DETONATOR_EXPIRATION_TIME

  #----------------------------------------------------------------------------

  ## Returns a time until the bomb explodes by itself.

  def time_until_explosion(self):
    return self.explodes_in + self.detonator_time - self.time_of_existence

  #----------------------------------------------------------------------------

  def explodes(self):
    if not self.has_exploded:
      self.player.bomb_exploded()
      self.has_exploded = True

#==============================================================================

## Represents a flame coming off of an exploding bomb.

class Flame(object):

  #----------------------------------------------------------------------------

  def __init__(self):
    self.player = None               ##< reference to player to which the exploding bomb belonged
    self.time_to_burnout = 1000      ##< time in ms till the flame disappears
    self.direction = "all"           ##< string representation of the flame direction

#==============================================================================

class MapTile(object):
  TILE_FLOOR = 0                     ##< walkable map tile
  TILE_BLOCK = 1                     ##< non-walkable but destroyable map tile
  TILE_WALL = 2                      ##< non-walkable and non-destroyable map tile
  
  SPECIAL_OBJECT_TRAMPOLINE = 0
  SPECIAL_OBJECT_TELEPORT_A = 1
  SPECIAL_OBJECT_TELEPORT_B = 2
  SPECIAL_OBJECT_ARROW_UP = 3
  SPECIAL_OBJECT_ARROW_RIGHT = 4
  SPECIAL_OBJECT_ARROW_DOWN = 5
  SPECIAL_OBJECT_ARROW_LEFT = 6
  SPECIAL_OBJECT_LAVA = 7

  #----------------------------------------------------------------------------

  def __init__(self, coordinates):
    self.kind = MapTile.TILE_FLOOR
    self.flames = []
    self.coordinates = coordinates
    self.to_be_destroyed = False     ##< Flag that marks the tile to be destroyed after the flames go out.
    self.item = None                 ##< Item that's present on the file
    self.special_object = None       ##< special object present on the tile, like trampoline or teleport
    self.destination_teleport = None ##< in case of special_object equal to SPECIAL_OBJECT_TELEPORT_A or SPECIAL_OBJECT_TELEPORT_B holds the destionation teleport tile coordinates

  def shouldnt_walk(self):
    return self.kind in [MapTile.TILE_WALL,MapTile.TILE_BLOCK] or len(self.flames) >= 1 or self.special_object == MapTile.SPECIAL_OBJECT_LAVA

#==============================================================================

## Holds and manipulates the map data including the players, bombs etc.

class GameMap(object):
  MAP_WIDTH = 15
  MAP_HEIGHT = 11
  WALL_MARGIN_HORIZONTAL = 0.2
  WALL_MARGIN_VERTICAL = 0.4
  
  COLLISION_BORDER_UP = 0       ##< position is inside upper border with non-walkable tile
  COLLISION_BORDER_RIGHT = 1    ##< position is inside right border with non-walkable tile
  COLLISION_BORDER_DOWN = 2     ##< position is inside bottom border with non-walkable tile
  COLLISION_BORDER_LEFT = 3     ##< position is inside left border with non-walkable tile
  COLLISION_TOTAL = 4           ##< position is inside non-walkable tile
  COLLISION_NONE = 5            ##< no collision

  ITEM_BOMB = 0
  ITEM_FLAME = 1
  ITEM_SUPERFLAME = 2
  ITEM_SPEEDUP = 3
  ITEM_DISEASE = 4
  ITEM_RANDOM = 5
  ITEM_SPRING = 6
  ITEM_SHOE = 7
  ITEM_MULTIBOMB = 8
  ITEM_BOXING_GLOVE = 9
  ITEM_DETONATOR = 10
  ITEM_THROWING_GLOVE = 11
  
  SAFE_DANGER_VALUE = 5000     ##< time in ms, used in danger map to indicate safe tile
  
  GIVE_AWAY_DELAY = 3000       ##< after how many ms the items of dead players will be given away
  
  START_GAME_AFTER = 2500      ##< delay in ms before the game begins
  
  STATE_WAITING_TO_PLAY = 0    ##< players can't do anything yet
  STATE_PLAYING = 1            ##< game is being played
  STATE_FINISHING = 2          ##< game is over but the map is still being updated for a while after
  STATE_GAME_OVER = 3          ##< the game is definitely over and should no longer be updated
  
  EARTHQUAKE_DURATION = 10000

  #----------------------------------------------------------------------------
  
  ## Initialises a new map from map_data (string) and a PlaySetup object.

  def __init__(self, map_data, play_setup, game_number, max_games, all_items_cheat=False):
    # make the tiles array:
    self.danger_map_is_up_to_date = False                    # to regenerate danger map only when needed
    self.tiles = []
    self.starting_positions = [(0.0,0.0) for i in xrange(10)] # starting position for each player

    map_data = map_data.replace(" ","").replace("\n","")     # get rid of white characters

    string_split = map_data.split(";")

    self.environment_name = string_split[0]

    self.end_game_at = -1                          ##< time at which the map should go to STATE_GAME_OVER state
    self.start_game_at = GameMap.START_GAME_AFTER
    self.win_announced = False
    self.announce_win_at = -1
    self.state = GameMap.STATE_WAITING_TO_PLAY
    self.winner_team = -1                          ##< if map state is GameMap.STATE_GAME_OVER, this holds the winning team (-1 = draw)

    self.game_number = game_number
    self.max_games = max_games

    self.earthquake_time_left = 0

    self.time_from_start = 0                       ##< time in ms from the start of the map, the time increases with each update (so time spent in game menu is excluded)

    block_tiles = []

    line = -1
    column = 0
    
    teleport_a_tile = None       # helper variables used to pair teleports
    teleport_b_tile = None
    self.number_of_blocks = 0    ##< says how many block tiles there are currently on the map

    for i in xrange(len(string_split[3])):
      tile_character = string_split[3][i]

      if i % GameMap.MAP_WIDTH == 0: # add new row
        line += 1
        column = 0
        self.tiles.append([])

      tile = MapTile((column,line))

      if tile_character == "x":
        tile.kind = MapTile.TILE_BLOCK
        block_tiles.append(tile)
      elif tile_character == "#":
        tile.kind = MapTile.TILE_WALL
      elif tile_character in ("u","r","d","l","U","R","D","L"):
        if tile_character.islower():
          tile.kind = MapTile.TILE_FLOOR
        else:
          tile.kind = MapTile.TILE_BLOCK
        
        tile_character = tile_character.lower()
        
        if tile_character == "u":
          tile.special_object = MapTile.SPECIAL_OBJECT_ARROW_UP
        elif tile_character == "r":
          tile.special_object = MapTile.SPECIAL_OBJECT_ARROW_RIGHT
        elif tile_character == "d":
          tile.special_object = MapTile.SPECIAL_OBJECT_ARROW_DOWN
        else:
          tile.special_object = MapTile.SPECIAL_OBJECT_ARROW_LEFT
      else:
        tile.kind = MapTile.TILE_FLOOR
        
        if tile_character == "A":
          tile.special_object = MapTile.SPECIAL_OBJECT_TELEPORT_A
          
          if teleport_a_tile == None:
            teleport_a_tile = tile
          else:
            tile.destination_teleport = teleport_a_tile.coordinates
            teleport_a_tile.destination_teleport = tile.coordinates
        elif tile_character == "B":
          tile.special_object = MapTile.SPECIAL_OBJECT_TELEPORT_A
          
          if teleport_b_tile == None:
            teleport_b_tile = tile
          else:
            tile.destination_teleport = teleport_b_tile.coordinates
            teleport_b_tile.destination_teleport = tile.coordinates
        elif tile_character == "T":
          tile.special_object = MapTile.SPECIAL_OBJECT_TRAMPOLINE
        elif tile_character == "V":
          tile.special_object = MapTile.SPECIAL_OBJECT_LAVA
        
      if tile.kind == MapTile.TILE_BLOCK:
        self.number_of_blocks += 1
        
      self.tiles[-1].append(tile)

      if tile_character.isdigit():
        self.starting_positions[int(tile_character)] = (float(column),float(line))

      column += 1

    # place items under the block tiles:
    
    for i in xrange(len(string_split[2])):
      random_tile = random.choice(block_tiles)
      random_tile.item = self.letter_to_item(string_split[2][i])
      block_tiles.remove(random_tile)

    # init danger map:
    
    self.danger_map = [[GameMap.SAFE_DANGER_VALUE for i in xrange(GameMap.MAP_WIDTH)] for j in xrange(GameMap.MAP_HEIGHT)]  ##< 2D array of times in ms for each square that
       
    # initialise players:

    self.players = []                      ##< list of players in the game
    self.players_by_numbers = {}           ##< mapping of numbers to players
    self.players_by_numbers[-1] = None

    player_slots = play_setup.get_slots()

    for i in xrange(len(player_slots)):
      if player_slots[i] != None:
        new_player = Player()
        new_player.set_number(i)
        new_player.set_team_number(player_slots[i][1])
        new_player.move_to_tile_center(self.starting_positions[i])
        self.players.append(new_player)
        self.players_by_numbers[i] = new_player
      else:
        self.players_by_numbers[i] = None
        
    # give players starting items:
    
    start_items_string = string_split[1] if not all_items_cheat else "bbbbbFkxtsssssmp"
    
    self.player_starting_items = []
    
    for i in xrange(len(start_items_string)):
      for player in self.players:
        item_to_give = self.letter_to_item(start_items_string[i])
        
        player.give_item(item_to_give)
      
      self.player_starting_items.append(item_to_give)
        
    self.bombs = []                   ##< bombs on the map
    self.sound_events = []            ##< list of currently happening sound event (see SoundPlayer class)
    self.animation_events = []        ##< list of animation events, tuples in format (animation_event, coordinates)
    self.items_to_give_away = []      ##< list of tuples in format (time_of_giveaway, list_of_items)

    self.create_disease_cloud_at = 0  ##< at what time (in ms) the disease clouds should be released

  #----------------------------------------------------------------------------

  def get_starting_items(self):
    return self.player_starting_items

  #----------------------------------------------------------------------------

  def get_starting_positions(self):
    return self.starting_positions

  #----------------------------------------------------------------------------

  ## Returns a tuple (game number, max games).
 
  def get_game_number_info(self):
    return (self.game_number,self.max_games)

  #----------------------------------------------------------------------------

  def start_earthquake(self):
    self.earthquake_time_left = GameMap.EARTHQUAKE_DURATION

  #----------------------------------------------------------------------------

  def earthquake_is_active(self):
    return self.earthquake_time_left > 0

  #----------------------------------------------------------------------------

  def get_number_of_block_tiles(self):
    return self.number_of_blocks

  #----------------------------------------------------------------------------

  ## Efficiently (lazily) gets a danger value of given tile. Danger value says
  #  how much time in ms has will pass until there will be a fire at the tile.

  def get_danger_value(self, tile_coordinates):
    if not self.danger_map_is_up_to_date:
      self.update_danger_map()
      self.danger_map_is_up_to_date = True
    
    if not self.tile_is_withing_map(tile_coordinates):
      return 0       # never walk outside map
    
    return self.danger_map[tile_coordinates[1]][tile_coordinates[0]]

  #----------------------------------------------------------------------------
  
  def tile_has_lava(self, tile_coordinates):
    if not self.tile_is_withing_map(tile_coordinates):
      return False
    
    return self.tiles[tile_coordinates[1]][tile_coordinates[0]].special_object == MapTile.SPECIAL_OBJECT_LAVA

  #----------------------------------------------------------------------------
  
  ## Gives away a set of given items (typically after a player dies). The items
  #  are spread randomly on the map floor tiles after a while.
  
  def give_away_items(self, items):
    self.items_to_give_away.append((pygame.time.get_ticks() + GameMap.GIVE_AWAY_DELAY,items))

  #----------------------------------------------------------------------------
  
  def update_danger_map(self):
    # reset the map:
    self.danger_map = [map(lambda tile: 0 if tile.shouldnt_walk() else GameMap.SAFE_DANGER_VALUE, tile_row) for tile_row in self.tiles]

    for bomb in self.bombs:
      bomb_tile = bomb.get_tile_position()
      
      time_until_explosion = bomb.time_until_explosion()
      
      if bomb.has_detonator():           # detonator = bad
        time_until_explosion = 100
      
      self.danger_map[bomb_tile[1]][bomb_tile[0]] = min(self.danger_map[bomb_tile[1]][bomb_tile[0]],time_until_explosion)

                         # up                              right                            down                             left
      position         = [[bomb_tile[0],bomb_tile[1] - 1], [bomb_tile[0] + 1,bomb_tile[1]], [bomb_tile[0],bomb_tile[1] + 1], [bomb_tile[0] - 1,bomb_tile[1]]]
      flame_stop       = [False,                           False,                           False,                           False]
      tile_increment   = [(0,-1),                          (1,0),                           (0,1),                           (-1,0)]
    
      for i in xrange(bomb.flame_length):
        for direction in (0,1,2,3):
          if flame_stop[direction]:
            continue
        
          if not self.tile_is_walkable(position[direction]) or not self.tile_is_withing_map(position[direction]):
            flame_stop[direction] = True
            continue
          
          current_tile = position[direction]
          
          self.danger_map[current_tile[1]][current_tile[0]] = min(self.danger_map[current_tile[1]][current_tile[0]],time_until_explosion)
          position[direction][0] += tile_increment[direction][0] 
          position[direction][1] += tile_increment[direction][1]

  #----------------------------------------------------------------------------
          
  def add_sound_event(self, sound_event):
    self.sound_events.append(sound_event)

  #----------------------------------------------------------------------------
    
  def add_animation_event(self, animation_event, coordinates):    
    self.animation_events.append((animation_event,coordinates))

  #----------------------------------------------------------------------------
    
  def get_tile_at(self, tile_coordinates):
    if self.tile_is_withing_map(tile_coordinates):
      return self.tiles[tile_coordinates[1]][tile_coordinates[0]]
    
    return None

  #----------------------------------------------------------------------------
    
  def get_and_clear_sound_events(self):
    result = self.sound_events[:]             # copy of the list
    self.sound_events = []
    return result

  #----------------------------------------------------------------------------

  def get_and_clear_animation_events(self):
    result = self.animation_events[:]         # copy of the list
    self.animation_events = []
    return result

  #----------------------------------------------------------------------------

  ## Converts given letter (as in map encoding string) to item code (see class constants).
  
  def letter_to_item(self, letter):
    mapping = {
      "f": GameMap.ITEM_FLAME,
      "F": GameMap.ITEM_SUPERFLAME,
      "b": GameMap.ITEM_BOMB,
      "k": GameMap.ITEM_SHOE,
      "s": GameMap.ITEM_SPEEDUP,
      "p": GameMap.ITEM_SPRING,
      "m": GameMap.ITEM_MULTIBOMB,
      "d": GameMap.ITEM_DISEASE,
      "r": GameMap.ITEM_RANDOM,
      "x": GameMap.ITEM_BOXING_GLOVE,
      "e": GameMap.ITEM_DETONATOR,
      "t": GameMap.ITEM_THROWING_GLOVE
      }

    return mapping[letter] if letter in mapping else -1

  #----------------------------------------------------------------------------

  def tile_has_flame(self, tile_coordinates):
    if not self.tile_is_withing_map(tile_coordinates):
      return False     # coordinates outside the map
    
    return len(self.tiles[tile_coordinates[1]][tile_coordinates[0]].flames) >= 1

  #----------------------------------------------------------------------------

  def tile_has_teleport(self, tile_coordinates):
    tile_coordinates = Positionable.position_to_tile(tile_coordinates)
    
    if not self.tile_is_withing_map(tile_coordinates):
      return False     # coordinates outside the map
    
    return self.tiles[tile_coordinates[1]][tile_coordinates[0]].special_object in (MapTile.SPECIAL_OBJECT_TELEPORT_A,MapTile.SPECIAL_OBJECT_TELEPORT_B)

  #----------------------------------------------------------------------------

  def bomb_on_tile(self, tile_coordinates):
    bombs = self.bombs_on_tile(tile_coordinates)
    
    if len(bombs) > 0:
      return bombs[0]
    
    return None

  #----------------------------------------------------------------------------

  ## Checks if there is a bomb at given tile (coordinates may be float or int).

  def tile_has_bomb(self, tile_coordinates):
    return self.bomb_on_tile(tile_coordinates) != None

  #----------------------------------------------------------------------------

  def get_players_at_tile(self, tile_coordinates):
    result = []
    
    for player in self.players:
      player_tile_position = player.get_tile_position()

      if not player.is_dead() and not player.is_in_air() and player_tile_position[0] == tile_coordinates[0] and player_tile_position[1] == tile_coordinates[1]:
        result.append(player)
    
    return result

  #----------------------------------------------------------------------------

  def tile_has_player(self, tile_coordinates):
    return len(self.get_players_at_tile(tile_coordinates))

  #----------------------------------------------------------------------------

  ## Checks if given tile coordinates are within the map boundaries.

  def tile_is_withing_map(self, tile_coordinates):
    return tile_coordinates[0] >= 0 and tile_coordinates[1] >= 0 and tile_coordinates[0] <= GameMap.MAP_WIDTH - 1 and tile_coordinates[1] <= GameMap.MAP_HEIGHT - 1

  #----------------------------------------------------------------------------

  def tile_is_walkable(self, tile_coordinates):
    if not self.tile_is_withing_map(tile_coordinates):
      return False
    
    tile = self.tiles[tile_coordinates[1]][tile_coordinates[0]]
    return self.tile_is_withing_map(tile_coordinates) and (self.tiles[tile_coordinates[1]][tile_coordinates[0]].kind == MapTile.TILE_FLOOR or tile.to_be_destroyed) and not self.tile_has_bomb(tile_coordinates)

  #----------------------------------------------------------------------------

  ## Gets a collision type (see class constants) for given float position.

  def get_position_collision_type(self, position):
    tile_coordinates = Positionable.position_to_tile(position)
    
    if not self.tile_is_walkable(tile_coordinates):
      return GameMap.COLLISION_TOTAL
    
    position_within_tile = (position[0] % 1,position[1] % 1)
    
    if position_within_tile[1] < GameMap.WALL_MARGIN_HORIZONTAL:
      if not self.tile_is_walkable((tile_coordinates[0],tile_coordinates[1] - 1)):
        return GameMap.COLLISION_BORDER_UP
    elif position_within_tile[1] > 1.0 - GameMap.WALL_MARGIN_HORIZONTAL:
      if not self.tile_is_walkable((tile_coordinates[0],tile_coordinates[1] + 1)):
        return GameMap.COLLISION_BORDER_DOWN
      
    if position_within_tile[0] < GameMap.WALL_MARGIN_VERTICAL:
      if not self.tile_is_walkable((tile_coordinates[0] - 1,tile_coordinates[1])):
        return GameMap.COLLISION_BORDER_LEFT
    elif position_within_tile[0] > 1.0 - GameMap.WALL_MARGIN_VERTICAL:
      if not self.tile_is_walkable((tile_coordinates[0] + 1,tile_coordinates[1])):
        return GameMap.COLLISION_BORDER_RIGHT
    
    return GameMap.COLLISION_NONE

  #----------------------------------------------------------------------------

  def bombs_on_tile(self, tile_coordinates):
    result = []
    
    tile_coordinates = Positionable.position_to_tile(tile_coordinates)
    
    for bomb in self.bombs:
      bomb_tile_position = bomb.get_tile_position()

      if bomb.movement != Bomb.BOMB_FLYING and bomb_tile_position[0] == tile_coordinates[0] and bomb_tile_position[1] == tile_coordinates[1]:
        result.append(bomb)
      
    return result

  #----------------------------------------------------------------------------

  ## Gets time in ms spent in actual game from the start of the map.

  def get_map_time(self):
    return self.time_from_start

  #----------------------------------------------------------------------------

  ## Tells the map that given bomb is exploding, the map then creates
  #  flames from the bomb, the bomb is destroyed and players are informed.

  def bomb_explodes(self, bomb):
    self.add_sound_event(SoundPlayer.SOUND_EVENT_EXPLOSION)
    
    bomb_position = bomb.get_tile_position()
    
    new_flame = Flame()
    new_flame.player = bomb.player
    new_flame.direction = "all"
    
    self.tiles[bomb_position[1]][bomb_position[0]].flames.append(new_flame)
    
    # information relevant to flame spreading in each direction:
    
                     # up                    right                down                 left
    axis_position    = [bomb_position[1] - 1,bomb_position[0] + 1,bomb_position[1] + 1,bomb_position[0] - 1]
    flame_stop       = [False,               False,               False,               False]
    map_limit        = [0,                   GameMap.MAP_WIDTH - 1,   GameMap.MAP_HEIGHT - 1,  0]
    increment        = [-1,                  1,                   1,                   -1]
    goes_horizontaly = [False,               True,                False,               True]
    previous_flame   = [None,                None,                None,                None]
    
    # spread the flame in all 4 directions:

    for i in xrange(bomb.flame_length + 1):
      if i >= bomb.flame_length:
        flame_stop = [True, True, True, True]

      for direction in (0,1,2,3): # for each direction
        if flame_stop[direction]:  
          if previous_flame[direction] != None:   # flame stopped in previous iteration
            previous_flame[direction].direction = {0: "up", 1: "right", 2: "down", 3: "left"}[direction]
            previous_flame[direction] = None
        else:
          if ((increment[direction] == -1 and axis_position[direction] >= map_limit[direction]) or
            (increment[direction] == 1 and axis_position[direction] <= map_limit[direction])):
            # flame is inside the map here          
        
            if goes_horizontaly[direction]:
              tile_for_flame = self.tiles[bomb_position[1]][axis_position[direction]]
            else:
              tile_for_flame = self.tiles[axis_position[direction]][bomb_position[0]]
        
            if tile_for_flame.kind == MapTile.TILE_WALL:
              flame_stop[direction] = True
            else:
              new_flame2 = copy.copy(new_flame)
              new_flame2.direction = "horizontal" if goes_horizontaly[direction] else "vertical"
              tile_for_flame.flames.append(new_flame2)
            
              previous_flame[direction] = new_flame2
            
              if tile_for_flame.kind == MapTile.TILE_BLOCK:
                flame_stop[direction] = True
          else:
            flame_stop[direction] = True
          
        axis_position[direction] += increment[direction]
    
    bomb.explodes()
   
    if bomb in self.bombs:
      self.bombs.remove(bomb)

  #----------------------------------------------------------------------------

  def spread_items(self, items):
    possible_tiles = []
    
    for y in xrange(GameMap.MAP_HEIGHT):
      for x in xrange(GameMap.MAP_WIDTH):
        tile = self.tiles[y][x]
        
        if tile.kind == MapTile.TILE_FLOOR and tile.special_object == None and tile.item == None and not self.tile_has_player((x,y)):
          possible_tiles.append(tile)
          
    for item in items:
      if len(possible_tiles) == 0:
        break                              # no more tiles to place items on => end
      
      tile = random.choice(possible_tiles)
      tile.item = item
      
      possible_tiles.remove(tile)

  #----------------------------------------------------------------------------

  def __update_bombs(self, dt):
    i = 0

    while i < len(self.bombs):    # update all bombs
      bomb = self.bombs[i]
      
      if bomb.has_exploded:       # just in case
        self.bombs.remove(bomb)
        continue
      
      bomb.time_of_existence += dt
            
      bomb_position = bomb.get_position()
      bomb_tile = bomb.get_tile_position()

      if bomb.movement != Bomb.BOMB_FLYING and bomb.time_of_existence > bomb.explodes_in + bomb.detonator_time: # bomb explodes
        self.bomb_explodes(bomb)
        continue
      elif bomb.movement != Bomb.BOMB_FLYING and self.tiles[bomb_tile[1]][bomb_tile[0]].special_object == MapTile.SPECIAL_OBJECT_LAVA and bomb.is_near_tile_center():
        self.bomb_explodes(bomb)
        continue
      else:
        i += 1
      
      if bomb.movement != Bomb.BOMB_NO_MOVEMENT:
        if bomb.movement == Bomb.BOMB_FLYING:
          distance_to_travel = dt / 1000.0 * Bomb.FLYING_SPEED
          bomb.flight_info.distance_travelled += distance_to_travel
          
          if bomb.flight_info.distance_travelled >= bomb.flight_info.total_distance_to_travel:
            bomb_tile = bomb.get_tile_position()
            self.add_sound_event(SoundPlayer.SOUND_EVENT_BOMB_PUT)

            if not self.tile_is_walkable(bomb_tile) or self.tile_has_player(bomb_tile) or self.tile_has_teleport(bomb_tile):
              destination_tile = (bomb_tile[0] + bomb.flight_info.direction[0],bomb_tile[1] + bomb.flight_info.direction[1])
              bomb.send_flying(destination_tile)
            else:        # bomb lands
              bomb.movement = Bomb.BOMB_NO_MOVEMENT
              self.get_tile_at(bomb_tile).item = None        
        else:            # bomb rolling          
          if bomb.is_near_tile_center():
            object_at_tile = self.tiles[bomb_tile[1]][bomb_tile[0]].special_object
          
            redirected = False
          
            if object_at_tile == MapTile.SPECIAL_OBJECT_ARROW_UP and bomb.movement != Bomb.BOMB_ROLLING_UP:
              bomb.movement = Bomb.BOMB_ROLLING_UP
              bomb.set_position((bomb_tile[0] + 0.5,bomb_tile[1]))  # aline with x axis
              redirected = True
            elif object_at_tile == MapTile.SPECIAL_OBJECT_ARROW_RIGHT and bomb.movement != Bomb.BOMB_ROLLING_RIGHT:
              bomb.movement = Bomb.BOMB_ROLLING_RIGHT
              bomb.set_position((bomb_position[0],bomb_tile[1] + 0.5))
              redirected = True
            elif object_at_tile == MapTile.SPECIAL_OBJECT_ARROW_DOWN and bomb.movement != Bomb.BOMB_ROLLING_DOWN:
              bomb.movement = Bomb.BOMB_ROLLING_DOWN
              bomb.set_position((bomb_tile[0] + 0.5,bomb_position[1]))
              redirected = True
            elif object_at_tile == MapTile.SPECIAL_OBJECT_ARROW_LEFT and bomb.movement != Bomb.BOMB_ROLLING_LEFT:
              bomb.movement = Bomb.BOMB_ROLLING_LEFT
              bomb.set_position((bomb_position[0],bomb_tile[1] + 0.5))
              redirected = True
        
            if redirected:
              bomb_position = bomb.get_position()
              
          if self.tiles[bomb_tile[1]][bomb_tile[0]].item != None:   # rolling bomb destroys items
            self.tiles[bomb_tile[1]][bomb_tile[0]].item = None
        
          bomb_position_within_tile = (bomb_position[0] % 1,bomb_position[1] % 1) 
          check_collision = False
          forward_tile = None
          distance_to_travel = dt / 1000.0 * Bomb.ROLLING_SPEED
          
          helper_boundaries = (0.5,0.9)
          helper_boundaries2 = (1 - helper_boundaries[1],1 - helper_boundaries[0])
        
          opposite_direction = Bomb.BOMB_NO_MOVEMENT
          
          if bomb.movement == Bomb.BOMB_ROLLING_UP:
            bomb.set_position((bomb_position[0],bomb_position[1] - distance_to_travel))
            opposite_direction = Bomb.BOMB_ROLLING_DOWN
        
            if helper_boundaries2[0] < bomb_position_within_tile[1] < helper_boundaries2[1]:
              check_collision = True
              forward_tile = (bomb_tile[0],bomb_tile[1] - 1)
        
          elif bomb.movement == Bomb.BOMB_ROLLING_RIGHT:
            bomb.set_position((bomb_position[0] + distance_to_travel,bomb_position[1]))
            opposite_direction = Bomb.BOMB_ROLLING_LEFT
          
            if helper_boundaries[0] < bomb_position_within_tile[0] < helper_boundaries[1]:
              check_collision = True
              forward_tile = (bomb_tile[0] + 1,bomb_tile[1])
          
          elif bomb.movement == Bomb.BOMB_ROLLING_DOWN:
            bomb.set_position((bomb_position[0],bomb_position[1] + distance_to_travel))
            opposite_direction = Bomb.BOMB_ROLLING_UP
          
            if helper_boundaries[0] < bomb_position_within_tile[1] < helper_boundaries[1]:
              check_collision = True
              forward_tile = (bomb_tile[0],bomb_tile[1] + 1)
          
          elif bomb.movement == Bomb.BOMB_ROLLING_LEFT:
            bomb.set_position((bomb_position[0] - distance_to_travel,bomb_position[1]))        
            opposite_direction = Bomb.BOMB_ROLLING_RIGHT

            if helper_boundaries2[0] < bomb_position_within_tile[0] < helper_boundaries2[1]:
              check_collision = True
              forward_tile = (bomb_tile[0] - 1,bomb_tile[1])

          if check_collision and (not self.tile_is_walkable(forward_tile) or self.tile_has_player(forward_tile) or self.tile_has_teleport(forward_tile)):
            bomb.move_to_tile_center()          
          
            if bomb.has_spring:
              bomb.movement = opposite_direction
              self.add_sound_event(SoundPlayer.SOUND_EVENT_SPRING)
            else:
              bomb.movement = Bomb.BOMB_NO_MOVEMENT
              self.add_sound_event(SoundPlayer.SOUND_EVENT_KICK)

  #----------------------------------------------------------------------------

  def __update_players(self, dt, immortal_player_numbers):
    time_now = pygame.time.get_ticks()
    release_disease_cloud = False
    
    if time_now > self.create_disease_cloud_at:
      self.create_disease_cloud_at = time_now + 200     # release the cloud every 200 ms
      release_disease_cloud = True
    
    for player in self.players:
      if player.is_dead():
        continue
      
      if release_disease_cloud and player.get_disease() != Player.DISEASE_NONE:
        self.add_animation_event(Renderer.ANIMATION_EVENT_DISEASE_CLOUD,Renderer.map_position_to_pixel_position(player.get_position(),(0,0)))
      
      if self.winning_color == -1:
        self.winning_color = player.get_team_number()
      elif self.winning_color != player.get_team_number():
        self.game_is_over = False
        
      player_tile_position = player.get_tile_position()
      player_tile = self.tiles[player_tile_position[1]][player_tile_position[0]]
      
      if player.get_state() != Player.STATE_IN_AIR and player.get_state != Player.STATE_TELEPORTING and (self.tile_has_flame(player_tile.coordinates) or self.tile_has_lava(player_tile.coordinates)):

        # if player immortality cheat isn't activated        
        if not (player.get_number() in immortal_player_numbers):
          flames = self.get_tile_at(player_tile.coordinates).flames
        
          # assign kill counts
        
          for flame in flames:
            increase_kills_by = 1 if flame.player != player else -1   # self kill decreases the kill count
            flame.player.set_kills(flame.player.get_kills() + increase_kills_by)
        
          player.kill(self)
          continue
      
      if player_tile.item != None:
        player.give_item(player_tile.item,self)
        player_tile.item = None
      
      if player.is_in_air():
        if player.get_state_time() > Player.JUMP_DURATION / 2:  # jump to destination tile in the middle of the flight
          player.move_to_tile_center(player.get_jump_destination())      
      elif player.is_teleporting():
        if player.get_state_time() > Player.TELEPORT_DURATION / 2:
          player.move_to_tile_center(player.get_teleport_destination())
      elif player_tile.special_object == MapTile.SPECIAL_OBJECT_TRAMPOLINE and player.is_near_tile_center():
        player.send_to_air(self)
      elif (player_tile.special_object == MapTile.SPECIAL_OBJECT_TELEPORT_A or player_tile.special_object == MapTile.SPECIAL_OBJECT_TELEPORT_B) and player.is_near_tile_center():
        player.teleport(self)
      elif player.get_disease() != Player.DISEASE_NONE:
        players_at_tile = self.get_players_at_tile(player_tile_position)

        transmitted = False

        for player_at_tile in players_at_tile:
          if player_at_tile.get_disease() == Player.DISEASE_NONE:
            transmitted = True
            player_at_tile.set_disease(player.get_disease(),player.get_disease_time())  # transmit disease
          
        #if transmitted and random.randint(0,2) == 0:
        #  self.add_sound_event(SoundPlayer.SOUND_EVENT_GO_AWAY)

  #----------------------------------------------------------------------------

  ## Updates some things on the map that change with time.

  def update(self, dt, immortal_player_numbers=[]):
    self.time_from_start += dt
    
    self.danger_map_is_up_to_date = False    # reset this each frame
    
    i = 0
    
    self.earthquake_time_left = max(0,self.earthquake_time_left - dt)
    
    while i < len(self.items_to_give_away):  # giving away items of dead players
      item = self.items_to_give_away[i]
      
      if self.time_from_start >= item[0]:
        self.spread_items(item[1])
        self.items_to_give_away.remove(item)
        
        debug_log("giving away items")
          
      i += 1

    self.__update_bombs(dt)

    for line in self.tiles:
      for tile in line:
        if tile.to_be_destroyed and tile.kind == MapTile.TILE_BLOCK and not self.tile_has_flame(tile.coordinates):
          tile.kind = MapTile.TILE_FLOOR
          self.number_of_blocks -= 1
          tile.to_be_destroyed = False
        
        i = 0
        
        while True:
          if i >= len(tile.flames):
            break
          
          if tile.kind == MapTile.TILE_BLOCK:  # flame on a block tile -> destroy the block
            tile.to_be_destroyed = True
          elif tile.kind == MapTile.TILE_FLOOR and tile.item != None:
            tile.item = None                   # flame destroys the item
          
          bombs_inside_flame = self.bombs_on_tile(tile.coordinates)
          
          for bomb in bombs_inside_flame:      # bomb inside flame -> detonate it
            self.bomb_explodes(bomb)
          
          flame = tile.flames[i]
          
          flame.time_to_burnout -= dt
          
          if flame.time_to_burnout < 0:
            tile.flames.remove(flame)
      
          i += 1
    
    self.game_is_over = True
    self.winning_color = -1

    self.__update_players(dt,immortal_player_numbers)
          
    if self.state == GameMap.STATE_WAITING_TO_PLAY:  
      if self.time_from_start >= self.start_game_at:
        self.state = GameMap.STATE_PLAYING
        self.add_sound_event(SoundPlayer.SOUND_EVENT_GO)
    if self.state == GameMap.STATE_FINISHING:
      if self.time_from_start >= self.end_game_at:
        self.state = GameMap.STATE_GAME_OVER
      elif not self.win_announced:
        if self.time_from_start >= self.announce_win_at:
          self.add_sound_event(SoundPlayer.SOUND_EVENT_WIN_0 + self.winner_team)
          self.win_announced = True
    elif self.state != GameMap.STATE_GAME_OVER and self.game_is_over:
      self.end_game_at = self.time_from_start + 5000
      self.state = GameMap.STATE_FINISHING
      self.winner_team = self.winning_color
      self.announce_win_at = self.time_from_start + 2000
    
  #----------------------------------------------------------------------------

  def get_winner_team(self):
    return self.winner_team

  #----------------------------------------------------------------------------
    
  def get_state(self):
    return self.state

  #----------------------------------------------------------------------------
    
  def add_bomb(self, bomb):
    self.bombs.append(bomb)

  #----------------------------------------------------------------------------

  def get_bombs(self):
    return self.bombs

  #----------------------------------------------------------------------------

  def get_environment_name(self):
    return self.environment_name

  #----------------------------------------------------------------------------

  def get_players(self):
    return self.players

  #----------------------------------------------------------------------------

  ## Gets a dict that maps numbers to players (with Nones if player with given number doesn't exist).

  def get_players_by_numbers(self):
    return self.players_by_numbers

  #----------------------------------------------------------------------------

  def get_tiles(self):
    return self.tiles

  #----------------------------------------------------------------------------

  def __str__(self):
    result = ""

    for line in self.tiles:
      for tile in line:
        if tile.kind == MapTile.TILE_FLOOR:
          result += " "
        elif tile.kind == MapTile.TILE_BLOCK:
          result += "x"
        else:
          result += "#"
  
      result += "\n"

    return result

#==============================================================================

## Defines how a game is set up, i.e. how many players
#  there are, what are the teams etc. Setup does not include
#  the selected map.

class PlaySetup(object):
  MAX_GAMES = 20

  #----------------------------------------------------------------------------
  
  def __init__(self):
    self.player_slots = [None for i in xrange(10)]    ##< player slots: (player_number, team_color),
                                                     #   negative player_number = AI, slot index ~ player color index
    self.number_of_games = 10
    
    # default setup, player 0 vs 3 AI players:
    self.player_slots[0] = (0,0)
    self.player_slots[1] = (-1,1)
    self.player_slots[2] = (-1,2)
    self.player_slots[3] = (-1,3)

  #----------------------------------------------------------------------------

  def get_slots(self):
    return self.player_slots

  #----------------------------------------------------------------------------

  def get_number_of_games(self):
    return self.number_of_games

  #----------------------------------------------------------------------------

  def set_number_of_games(self, number_of_games):
    self.number_of_games = number_of_games

  #----------------------------------------------------------------------------
  
  def increase_number_of_games(self):
    self.number_of_games = self.number_of_games % PlaySetup.MAX_GAMES + 1

  #----------------------------------------------------------------------------
  
  def decrease_number_of_games(self):
    self.number_of_games = (self.number_of_games - 2) % PlaySetup.MAX_GAMES + 1
   
#==============================================================================

## Something that can be saved/loaded to/from string.
  
class StringSerializable(object):

  #----------------------------------------------------------------------------

  def save_to_string(self):
    return ""

  #----------------------------------------------------------------------------
  
  def load_from_string(self, input_string):
    return

  #----------------------------------------------------------------------------
  
  def save_to_file(self, filename):
    text_file = open(filename,"w")
    text_file.write(self.save_to_string())
    text_file.close()

  #----------------------------------------------------------------------------
  
  def load_from_file(self, filename):
    with open(filename,"r") as text_file:
      self.load_from_string(text_file.read())
    
#==============================================================================

## Handles conversion of keyboard events to actions of players, plus general
#  actions (such as menu, ...). Also managed some more complex input processing.

class PlayerKeyMaps(StringSerializable):
  ACTION_UP = 0
  ACTION_RIGHT = 1
  ACTION_DOWN = 2
  ACTION_LEFT = 3
  ACTION_BOMB = 4
  ACTION_SPECIAL = 5
  ACTION_MENU = 6                ##< brings up the main menu 
  ACTION_BOMB_DOUBLE = 7
  
  MOUSE_CONTROL_UP = -1
  MOUSE_CONTROL_RIGHT = -2
  MOUSE_CONTROL_DOWN = -3
  MOUSE_CONTROL_LEFT = -4
  MOUSE_CONTROL_BUTTON_L = -5
  MOUSE_CONTROL_BUTTON_M = -6
  MOUSE_CONTROL_BUTTON_R = -7
  
  MOUSE_CONTROL_BIAS = 2         ##< mouse movement bias in pixels
  
  TYPED_STRING_BUFFER_LENGTH = 15
  
  ACTION_NAMES = {
    ACTION_UP : "up",
    ACTION_RIGHT : "right",
    ACTION_DOWN : "down",
    ACTION_LEFT : "left",
    ACTION_BOMB : "bomb",
    ACTION_SPECIAL : "special",
    ACTION_MENU : "menu",
    ACTION_BOMB_DOUBLE : "bomb double" 
    }
  
  MOUSE_ACTION_NAMES = {
    MOUSE_CONTROL_UP : "m up",
    MOUSE_CONTROL_RIGHT : "m right",
    MOUSE_CONTROL_DOWN : "m down",
    MOUSE_CONTROL_LEFT : "m left",
    MOUSE_CONTROL_BUTTON_L : "m L",
    MOUSE_CONTROL_BUTTON_M : "m M",
    MOUSE_CONTROL_BUTTON_R : "m R"
    }
  
  MOUSE_CONTROL_SMOOTH_OUT_TIME = 50

  #----------------------------------------------------------------------------

  def __init__(self):
    self.key_maps = {}  ##< maps keys to tuples of a format: (player_number, action), for general actions player_number will be -1
    
    self.bomb_key_last_pressed_time = [0 for i in xrange(10)]  ##< for bomb double press detection
    self.bomb_key_previous_state = [False for i in xrange(10)] ##< for bomb double press detection

    self.allow_mouse_control = False    ##< if true, player movement by mouse is allowed, otherwise not

    mouse_control_constants = [
      PlayerKeyMaps.MOUSE_CONTROL_UP,
      PlayerKeyMaps.MOUSE_CONTROL_RIGHT,
      PlayerKeyMaps.MOUSE_CONTROL_DOWN,
      PlayerKeyMaps.MOUSE_CONTROL_LEFT,
      PlayerKeyMaps.MOUSE_CONTROL_BUTTON_L,
      PlayerKeyMaps.MOUSE_CONTROL_BUTTON_M,
      PlayerKeyMaps.MOUSE_CONTROL_BUTTON_R]

    self.mouse_control_states = {}
    self.mouse_control_keep_until = {}  ##< time in which specified control was activated,
                                        #   helps keeping them active for a certain amount of time to smooth them out 
    mouse_control_states = {
      PlayerKeyMaps.MOUSE_CONTROL_UP : False,
      PlayerKeyMaps.MOUSE_CONTROL_RIGHT : False,
      PlayerKeyMaps.MOUSE_CONTROL_DOWN : False,
      PlayerKeyMaps.MOUSE_CONTROL_LEFT : False,
      PlayerKeyMaps.MOUSE_CONTROL_BUTTON_L : False,
      PlayerKeyMaps.MOUSE_CONTROL_BUTTON_M : False,
      PlayerKeyMaps.MOUSE_CONTROL_BUTTON_R : False
      }

    for item in mouse_control_constants:
      self.mouse_control_states[item] = False
      self.mouse_control_keep_until[item] = 0
      
    self.mouse_button_states = [False,False,False,False,False] ##< (left, right, middle, wheel up, wheel down)
    self.previous_mouse_button_states = [False,False,False,False,False]  
    self.last_mouse_update_frame = -1
    
    
    self.name_code_mapping = {}     # holds a mapping of key names to pygame key codes, since pygame itself offers no such functionality   
    keys_pressed = pygame.key.get_pressed()
    
    for key_code in xrange(len(keys_pressed)):
      self.name_code_mapping[pygame.key.name(key_code)] = key_code
     
    self.typed_string_buffer = [" " for i in xrange(PlayerKeyMaps.TYPED_STRING_BUFFER_LENGTH)]
     
    self.reset()

  #----------------------------------------------------------------------------

  def pygame_name_to_key_code(self, pygame_name):
    try:
      return self.name_code_mapping[pygame_name]
    except KeyError:
      return -1

  #----------------------------------------------------------------------------

  ## Returns a state of mouse buttons including mouse wheel (unlike pygame.mouse.get_pressed) as
  #  a tuple (left, right, middle, wheel up, wheel down).

  def get_mouse_button_states(self):
    return self.mouse_button_states

  #----------------------------------------------------------------------------
    
  ## Returns a tuple corresponding to mouse buttons (same as get_mouse_button_states) where each
  #  item says if the button has been pressed since the last frame.
    
  def get_mouse_button_events(self):
    result = []
    
    for i in xrange(5):
      result.append(self.mouse_button_states[i] and not self.previous_mouse_button_states[i])
    
    return result

  #----------------------------------------------------------------------------
    
  ## This informs the object abour pygame events so it can keep track of some input states.
    
  def process_pygame_events(self, pygame_events, frame_number):
    if frame_number != self.last_mouse_update_frame:
      # first time calling this function this frame => reset states
    
      for i in xrange(5):      # for each of 5 buttons
        self.previous_mouse_button_states[i] = self.mouse_button_states[i]
    
      button_states = pygame.mouse.get_pressed()
    
      self.mouse_button_states[0] = button_states[0]
      self.mouse_button_states[1] = button_states[2]
      self.mouse_button_states[2] = button_states[1]
      self.mouse_button_states[3] = False
      self.mouse_button_states[4] = False     
      self.last_mouse_update_frame = frame_number

    for pygame_event in pygame_events:
      if pygame_event.type == pygame.MOUSEBUTTONDOWN:
        if pygame_event.button == 4:
          self.mouse_button_states[3] = True
        elif pygame_event.button == 5:
          self.mouse_button_states[4] = True
      elif pygame_event.type == pygame.KEYDOWN:
        try:
          self.typed_string_buffer = self.typed_string_buffer[1:]
          self.typed_string_buffer.append(chr(pygame_event.key))
        except Exception:
          debug_log("couldn't append typed character to the buffer")

  #----------------------------------------------------------------------------
        
  def clear_typing_buffer(self):
    self.typed_string_buffer = [" " for i in xrange(PlayerKeyMaps.TYPED_STRING_BUFFER_LENGTH)]

  #----------------------------------------------------------------------------
        
  def string_was_typed(self, string):
    return str.find("".join(self.typed_string_buffer),string) >= 0

  #----------------------------------------------------------------------------
        
  def reset(self):
    self.allow_control_by_mouse(False)
    self.set_player_key_map(0,pygame.K_w,pygame.K_d,pygame.K_s,pygame.K_a,pygame.K_c,pygame.K_v)
    self.set_player_key_map(1,pygame.K_UP,pygame.K_RIGHT,pygame.K_DOWN,pygame.K_LEFT,pygame.K_RETURN,pygame.K_RSHIFT)
    self.set_player_key_map(2,pygame.K_u,pygame.K_k,pygame.K_j,pygame.K_h,pygame.K_o,pygame.K_p)
    self.set_player_key_map(3,PlayerKeyMaps.MOUSE_CONTROL_UP,PlayerKeyMaps.MOUSE_CONTROL_RIGHT,PlayerKeyMaps.MOUSE_CONTROL_DOWN,PlayerKeyMaps.MOUSE_CONTROL_LEFT,PlayerKeyMaps.MOUSE_CONTROL_BUTTON_L,PlayerKeyMaps.MOUSE_CONTROL_BUTTON_R)
    self.set_special_key_map(pygame.K_ESCAPE)

  #----------------------------------------------------------------------------

  ##< Gets a direction of given action (0 - up, 1 - right, 2 - down, 3 - left).

  @staticmethod
  def get_action_direction_number(action):
    if action == PlayerKeyMaps.ACTION_UP:
      return 0
    elif action == PlayerKeyMaps.ACTION_RIGHT:
      return 1
    elif action == PlayerKeyMaps.ACTION_DOWN:
      return 2
    elif action == PlayerKeyMaps.ACTION_LEFT:
      return 3
    
    return 0

  #----------------------------------------------------------------------------

  @staticmethod
  def get_opposite_action(action):
    if action == PlayerKeyMaps.ACTION_UP:
      return PlayerKeyMaps.ACTION_DOWN
    elif action == PlayerKeyMaps.ACTION_RIGHT:
      return PlayerKeyMaps.ACTION_LEFT
    elif action == PlayerKeyMaps.ACTION_DOWN:
      return PlayerKeyMaps.ACTION_UP
    elif action == PlayerKeyMaps.ACTION_LEFT:
      return PlayerKeyMaps.ACTION_RIGHT
    
    return action

  #----------------------------------------------------------------------------

  @staticmethod
  def key_to_string(key):
    if key == None:
      return "none"
    
    if key in PlayerKeyMaps.MOUSE_ACTION_NAMES:
      result = PlayerKeyMaps.MOUSE_ACTION_NAMES[key]
    else:
      result = pygame.key.name(key)
    
      if result == "unknown key":
        result = str(key)
    
    return result   

  #----------------------------------------------------------------------------

  def set_one_key_map(self, key, player_number, action):
    if key != None:
      self.key_maps[key] = (player_number,action)
      
      to_be_deleted = []
      
      for item in self.key_maps:     # get rid of possible collissions
        if item != key and self.key_maps[item] == (player_number,action):
          to_be_deleted.append(item)
          
      for item in to_be_deleted:
        del self.key_maps[item]

  #----------------------------------------------------------------------------

  ## Sets a key mapping for a player of specified (non-negative) number.

  def set_player_key_map(self, player_number, key_up, key_right, key_down, key_left, key_bomb, key_special):
    self.set_one_key_map(key_up,player_number,PlayerKeyMaps.ACTION_UP)
    self.set_one_key_map(key_right,player_number,PlayerKeyMaps.ACTION_RIGHT)
    self.set_one_key_map(key_down,player_number,PlayerKeyMaps.ACTION_DOWN)
    self.set_one_key_map(key_left,player_number,PlayerKeyMaps.ACTION_LEFT)
    self.set_one_key_map(key_bomb,player_number,PlayerKeyMaps.ACTION_BOMB)
    self.set_one_key_map(key_special,player_number,PlayerKeyMaps.ACTION_SPECIAL)

  #----------------------------------------------------------------------------

  ## Gets a dict that says how keys are mapped for a specific player. Format: {action_code : key_code, ...}, the
  #  dict will contain all actions and possibly None values for unmapped actions.

  def get_players_key_mapping(self, player_number):
    result = {action : None for action in (
      PlayerKeyMaps.ACTION_UP,
      PlayerKeyMaps.ACTION_RIGHT,
      PlayerKeyMaps.ACTION_DOWN,
      PlayerKeyMaps.ACTION_LEFT,
      PlayerKeyMaps.ACTION_BOMB,
      PlayerKeyMaps.ACTION_SPECIAL)}
    
    for key in self.key_maps:
      if self.key_maps[key][0] == player_number:
        result[self.key_maps[key][1]] = key
    
    return result

  #----------------------------------------------------------------------------

  def allow_control_by_mouse(self, allow=True):
   self.allow_mouse_control = allow

  #----------------------------------------------------------------------------

  def set_special_key_map(self, key_menu):
    self.set_one_key_map(key_menu,-1,PlayerKeyMaps.ACTION_MENU)

  #----------------------------------------------------------------------------

  ## Makes a human-readable string that represents the current key-mapping.

  def save_to_string(self):
    result = ""

    for i in xrange(Game.NUMBER_OF_CONTROLLED_PLAYERS):  # 4 players
      mapping = self.get_players_key_mapping(i)
      
      for action in mapping:
        result += str(i + 1) + " " + PlayerKeyMaps.ACTION_NAMES[action] + ": " + str(mapping[action]) + "\n"

    result += PlayerKeyMaps.ACTION_NAMES[PlayerKeyMaps.ACTION_MENU] + ": " + str(self.get_menu_key_map())
    
    return result

  #----------------------------------------------------------------------------
    
  ## Loads the mapping from string produced by save_to_string(...).
    
  def load_from_string(self, input_string):
    self.key_maps = {}
    
    lines = input_string.split("\n")
    
    for line in lines:
      line = line.lstrip().rstrip()
      
      try:
        key = int(line[line.find(":") + 1:])
      except Exception as e:
        key = None
      
      if line.find(PlayerKeyMaps.ACTION_NAMES[PlayerKeyMaps.ACTION_MENU]) == 0:
        self.set_one_key_map(key,-1,PlayerKeyMaps.ACTION_MENU)
      else:
        player_number = int(line[0]) - 1
        action_name = line[2:line.find(":")]
        
        action = None
        
        for helper_action in PlayerKeyMaps.ACTION_NAMES:
          if PlayerKeyMaps.ACTION_NAMES[helper_action] == action_name:
            action = helper_action
            break
      
        self.set_one_key_map(key,player_number,action)

  #----------------------------------------------------------------------------
    
  def get_menu_key_map(self):
    for key in self.key_maps:
      if self.key_maps[key][0] == -1:
        return key
      
    return None

  #----------------------------------------------------------------------------

  ## Returns a list of mouse control actions currently being performed (if mouse
  #  control is not allowed, the list will always be empty)

  def get_current_mouse_control_states(self):
    result = []
    
    if not self.allow_mouse_control:
      return result
    
    for mouse_action in self.mouse_control_states:
      if self.mouse_control_states[mouse_action]:
        result.append(mouse_action)
      
    return result

  #----------------------------------------------------------------------------

  ## From currently pressed keys makes a list of actions being currently performed and
  #  returns it, format: (player_number, action).

  def get_current_actions(self):
    keys_pressed = pygame.key.get_pressed()

    result = []

    reset_bomb_key_previous_state = [True for i in xrange(10)]

    # check mouse control:

    if self.allow_mouse_control:
      screen_center = (Renderer.get_screen_size()[0] / 2,Renderer.get_screen_size()[1] / 2)
      mouse_position = pygame.mouse.get_pos(screen_center)
      pressed = pygame.mouse.get_pressed()
      
      current_time = pygame.time.get_ticks()
      
      for item in self.mouse_control_states:    # reset
        if current_time > self.mouse_control_keep_until[item]:
          self.mouse_control_states[item] = False
      
      dx = abs(mouse_position[0] - screen_center[0])
      dy = abs(mouse_position[1] - screen_center[1])

      if dx > dy:            # choose the prevelant axis
        d_value = dx
        axis = 0
        axis_forward = PlayerKeyMaps.MOUSE_CONTROL_RIGHT
        axis_back = PlayerKeyMaps.MOUSE_CONTROL_LEFT
      else:
        axis = 1
        axis_forward = PlayerKeyMaps.MOUSE_CONTROL_DOWN
        axis_back = PlayerKeyMaps.MOUSE_CONTROL_UP
        d_value = dy

      if d_value > PlayerKeyMaps.MOUSE_CONTROL_BIAS:
        forward = mouse_position[axis] > screen_center[axis]
          
        self.mouse_control_states[axis_forward] = forward
        self.mouse_control_states[axis_back] = not forward          
        self.mouse_control_keep_until[axis_forward if forward else axis_back] = current_time + PlayerKeyMaps.MOUSE_CONTROL_SMOOTH_OUT_TIME  
        
      helper_buttons = (PlayerKeyMaps.MOUSE_CONTROL_BUTTON_L, PlayerKeyMaps.MOUSE_CONTROL_BUTTON_M, PlayerKeyMaps.MOUSE_CONTROL_BUTTON_R)

      for i in xrange(3):
        if pressed[i]:
          self.mouse_control_states[helper_buttons[i]] = True  
          self.mouse_control_keep_until[helper_buttons[i]] = current_time

      pygame.mouse.set_pos(screen_center)

    for key_code in self.key_maps:
      try:
        key_is_active = self.mouse_control_states[key_code] if key_code < 0 else keys_pressed[key_code]
      except IndexError as e:
        key_is_active = False
      
      if key_is_active:
        action_tuple = self.key_maps[key_code]  
        result.append(action_tuple)
        
        if action_tuple[1] == PlayerKeyMaps.ACTION_BOMB:
          player_number = action_tuple[0]
          
          if self.bomb_key_previous_state[player_number] == False and pygame.time.get_ticks() - self.bomb_key_last_pressed_time[player_number] < 200:
            result.append((player_number,PlayerKeyMaps.ACTION_BOMB_DOUBLE))
          
          self.bomb_key_last_pressed_time[player_number] = pygame.time.get_ticks()
          
          self.bomb_key_previous_state[player_number] = True
          reset_bomb_key_previous_state[player_number] = False

    for i in xrange(10):
      if reset_bomb_key_previous_state[i]:
        self.bomb_key_previous_state[i] = False

    return result

#==============================================================================

class SoundPlayer(object):
  # sound events used by other classes to tell soundplayer what to play
  
  SOUND_EVENT_EXPLOSION = 0
  SOUND_EVENT_BOMB_PUT = 1
  SOUND_EVENT_WALK = 2
  SOUND_EVENT_KICK = 3
  SOUND_EVENT_DIARRHEA = 4
  SOUND_EVENT_SPRING = 5
  SOUND_EVENT_SLOW = 6
  SOUND_EVENT_DISEASE = 7
  SOUND_EVENT_CLICK = 8
  SOUND_EVENT_THROW = 9
  SOUND_EVENT_TRAMPOLINE = 10
  SOUND_EVENT_TELEPORT = 11
  SOUND_EVENT_DEATH = 12
  SOUND_EVENT_WIN_0 = 13
  SOUND_EVENT_WIN_1 = 14
  SOUND_EVENT_WIN_2 = 15
  SOUND_EVENT_WIN_3 = 16
  SOUND_EVENT_WIN_4 = 17
  SOUND_EVENT_WIN_5 = 18
  SOUND_EVENT_WIN_6 = 19
  SOUND_EVENT_WIN_7 = 20
  SOUND_EVENT_WIN_8 = 21
  SOUND_EVENT_WIN_9 = 22
  SOUND_EVENT_GO_AWAY = 23
  SOUND_EVENT_GO = 24
  SOUND_EVENT_EARTHQUAKE = 25
  SOUND_EVENT_CONFIRM = 26

  #----------------------------------------------------------------------------
  
  def __init__(self):
    self.sound_volume = 0.5
    self.music_volume = 0.5
   
    self.sounds = {}
    self.sounds[SoundPlayer.SOUND_EVENT_EXPLOSION] = pygame.mixer.Sound(os.path.join(Game.RESOURCE_PATH,"explosion.wav"))
    self.sounds[SoundPlayer.SOUND_EVENT_BOMB_PUT] = pygame.mixer.Sound(os.path.join(Game.RESOURCE_PATH,"bomb.wav"))
    self.sounds[SoundPlayer.SOUND_EVENT_WALK] = pygame.mixer.Sound(os.path.join(Game.RESOURCE_PATH,"footsteps.wav"))
    self.sounds[SoundPlayer.SOUND_EVENT_KICK] = pygame.mixer.Sound(os.path.join(Game.RESOURCE_PATH,"kick.wav"))
    self.sounds[SoundPlayer.SOUND_EVENT_SPRING] = pygame.mixer.Sound(os.path.join(Game.RESOURCE_PATH,"spring.wav"))
    self.sounds[SoundPlayer.SOUND_EVENT_DIARRHEA] = pygame.mixer.Sound(os.path.join(Game.RESOURCE_PATH,"fart.wav"))
    self.sounds[SoundPlayer.SOUND_EVENT_SLOW] = pygame.mixer.Sound(os.path.join(Game.RESOURCE_PATH,"slow.wav"))
    self.sounds[SoundPlayer.SOUND_EVENT_DISEASE] = pygame.mixer.Sound(os.path.join(Game.RESOURCE_PATH,"disease.wav"))
    self.sounds[SoundPlayer.SOUND_EVENT_CLICK] = pygame.mixer.Sound(os.path.join(Game.RESOURCE_PATH,"click.wav"))
    self.sounds[SoundPlayer.SOUND_EVENT_THROW] = pygame.mixer.Sound(os.path.join(Game.RESOURCE_PATH,"throw.wav"))
    self.sounds[SoundPlayer.SOUND_EVENT_TRAMPOLINE] = pygame.mixer.Sound(os.path.join(Game.RESOURCE_PATH,"trampoline.wav"))
    self.sounds[SoundPlayer.SOUND_EVENT_TELEPORT] = pygame.mixer.Sound(os.path.join(Game.RESOURCE_PATH,"teleport.wav"))
    self.sounds[SoundPlayer.SOUND_EVENT_DEATH] = pygame.mixer.Sound(os.path.join(Game.RESOURCE_PATH,"death.wav"))
    self.sounds[SoundPlayer.SOUND_EVENT_GO] = pygame.mixer.Sound(os.path.join(Game.RESOURCE_PATH,"go.wav"))
    self.sounds[SoundPlayer.SOUND_EVENT_EARTHQUAKE] = pygame.mixer.Sound(os.path.join(Game.RESOURCE_PATH,"earthquake.wav"))
    self.sounds[SoundPlayer.SOUND_EVENT_CONFIRM] = pygame.mixer.Sound(os.path.join(Game.RESOURCE_PATH,"confirm.wav"))

    self.music_filenames = [
      "music_loyalty_freak_slow_pogo.wav",
      "music_anonymous420_start_to_play.wav",
      "music_anonymous420_first_step_for_your_tech.wav",
      "music_anonymous420_echo_blues_effect.wav",
      "music_loyalty_freak_music_enby.wav"
      ]
 
    self.current_music_index = -1
    
    self.playing_walk = False
    self.kick_last_played_time = 0

  #----------------------------------------------------------------------------
     
  def play_once(self, filename):
    sound = pygame.mixer.Sound(filename)
    sound.set_volume(self.sound_volume)
    sound.play()

  #----------------------------------------------------------------------------
   
  def set_music_volume(self, new_volume):
    self.music_volume = new_volume if new_volume > Settings.SOUND_VOLUME_THRESHOLD else 0
    
    debug_log("changing music volume to " + str(self.music_volume))
    
    if new_volume > Settings.SOUND_VOLUME_THRESHOLD:
      if not pygame.mixer.music.get_busy():
        pygame.mixer.music.play()
      
      pygame.mixer.music.set_volume(new_volume)
    else:
      pygame.mixer.music.stop()

  #----------------------------------------------------------------------------
      
  def set_sound_volume(self, new_volume):
    self.sound_volume = new_volume if new_volume > Settings.SOUND_VOLUME_THRESHOLD else 0
    
    debug_log("changing sound volume to " + str(self.sound_volume))
    
    for sound in self.sounds:
      self.sounds[sound].set_volume(self.sound_volume)

  #----------------------------------------------------------------------------
   
  def change_music(self):
    while True:
      new_music_index = random.randint(0,len(self.music_filenames) - 1)
      
      if new_music_index == self.current_music_index:
        continue
      
      break
    
    self.current_music_index = new_music_index
    
    music_name = self.music_filenames[self.current_music_index]
    
    debug_log("changing music to \"" + music_name + "\"")
    
    pygame.mixer.music.stop()
    pygame.mixer.music.load(os.path.join(Game.RESOURCE_PATH,music_name))
    pygame.mixer.music.set_volume(self.music_volume)
    pygame.mixer.music.play(-1)

  #----------------------------------------------------------------------------
   
  def play_sound_event(self,sound_event):
    self.process_events([sound_event])

  #----------------------------------------------------------------------------
   
  ## Processes a list of sound events (see class constants) by playing
  #  appropriate sounds.
    
  def process_events(self, sound_event_list): 
    stop_playing_walk = True
    
    for sound_event in sound_event_list: 
      if sound_event in (                        # simple sound play
        SoundPlayer.SOUND_EVENT_EXPLOSION,
        SoundPlayer.SOUND_EVENT_CLICK,
        SoundPlayer.SOUND_EVENT_BOMB_PUT,
        SoundPlayer.SOUND_EVENT_SPRING,
        SoundPlayer.SOUND_EVENT_DIARRHEA,
        SoundPlayer.SOUND_EVENT_SLOW,
        SoundPlayer.SOUND_EVENT_DISEASE,
        SoundPlayer.SOUND_EVENT_THROW,
        SoundPlayer.SOUND_EVENT_TRAMPOLINE,
        SoundPlayer.SOUND_EVENT_TELEPORT,
        SoundPlayer.SOUND_EVENT_DEATH,
        SoundPlayer.SOUND_EVENT_GO,
        SoundPlayer.SOUND_EVENT_EARTHQUAKE,
        SoundPlayer.SOUND_EVENT_CONFIRM
        ):
        self.sounds[sound_event].play()
    
      elif sound_event == SoundPlayer.SOUND_EVENT_WALK:
        if not self.playing_walk:
          self.sounds[SoundPlayer.SOUND_EVENT_WALK].play(loops=-1)
          self.playing_walk = True
        
        stop_playing_walk = False
      elif sound_event == SoundPlayer.SOUND_EVENT_KICK:
        time_now = pygame.time.get_ticks()
        
        if time_now > self.kick_last_played_time + 200:    # wait 200 ms before playing kick sound again        
          self.sounds[SoundPlayer.SOUND_EVENT_KICK].play()
          self.kick_last_played_time = time_now
      elif SoundPlayer.SOUND_EVENT_WIN_0 <= sound_event <= SoundPlayer.SOUND_EVENT_WIN_9:
        self.play_once(os.path.join(Game.RESOURCE_PATH,"win" + str(sound_event - SoundPlayer.SOUND_EVENT_WIN_0) + ".wav"))
      
    if self.playing_walk and stop_playing_walk:
      self.sounds[SoundPlayer.SOUND_EVENT_WALK].stop()
      self.playing_walk = False
    
  #  if not self.playing_walk = False
    
#==============================================================================

class Animation(object):

  #----------------------------------------------------------------------------

  def __init__(self, filename_prefix, start_number, end_number, filename_postfix, framerate = 10):
    self.framerate = framerate
    self.frame_time = 1000 / self.framerate
    
    self.frame_images = []
    
    for i in xrange(start_number,end_number + 1):
      self.frame_images.append(pygame.image.load(filename_prefix + str(i) + filename_postfix))
      
    self.playing_instances = []   ##< A set of playing animations, it is a list of tuples in
                                  #  a format: (pixel_coordinates, started_playing).     

  #----------------------------------------------------------------------------

  def play(self, coordinates):
    # convert center coordinates to top left coordinates:
    
    top_left = (coordinates[0] - self.frame_images[0].get_size()[0] / 2,coordinates[1] - self.frame_images[0].get_size()[1] / 2)
    self.playing_instances.append((top_left,pygame.time.get_ticks()))

  #----------------------------------------------------------------------------
    
  def draw(self, surface):
    i = 0
    
    time_now = pygame.time.get_ticks()
    
    while True:
      if i >= len(self.playing_instances):
        break
      
      playing_instance = self.playing_instances[i]
      
      frame = int((time_now - playing_instance[1]) / self.frame_time)
      
      if frame >= len(self.frame_images):
        self.playing_instances.remove(playing_instance)
        continue
        
      surface.blit(self.frame_images[frame],playing_instance[0])
      
      i += 1

#==============================================================================

## Abstract class representing a game menu. Menu item strings can contain formatting characters:
#
#  ^htmlcolorcode - sets the text color (HTML #rrggbb format,e.g. ^#2E44BF) from here to end of line or another formatting character
    
class Menu(object):
  MENU_STATE_SELECTING = 0                ##< still selecting an item
  MENU_STATE_CONFIRM = 1                  ##< menu has been confirmed
  MENU_STATE_CANCEL = 2                   ##< menu has been cancelled
  MENU_STATE_CONFIRM_PROMPT = 3           ##< prompting an action
  
  MENU_MAX_ITEMS_VISIBLE = 11

  #----------------------------------------------------------------------------
  
  def __init__(self,sound_player):
    self.text = ""
    self.selected_item = (0,0)            ##< row, column
    self.items = []                       ##< list (rows) of lists (column)
    self.menu_left = False
    self.confirm_prompt_result = None     ##< True, False or None
    self.scroll_position = 0              ##< index of the first visible row
    self.sound_player = sound_player
    self.action_keys_previous_state = {
      PlayerKeyMaps.ACTION_UP : True,
      PlayerKeyMaps.ACTION_RIGHT : True,
      PlayerKeyMaps.ACTION_DOWN : True,
      PlayerKeyMaps.ACTION_LEFT : True,
      PlayerKeyMaps.ACTION_BOMB : True,
      PlayerKeyMaps.ACTION_SPECIAL : True,
      PlayerKeyMaps.ACTION_BOMB_DOUBLE: True,
      PlayerKeyMaps.ACTION_MENU : True}        ##< to detect single key presses, the values have to be True in order not to rect immediatelly upon entering the menu
    self.state = Menu.MENU_STATE_SELECTING
    pass

  #----------------------------------------------------------------------------

  def get_scroll_position(self):
    return self.scroll_position

  #----------------------------------------------------------------------------

  def get_state(self):
    return self.state

  #----------------------------------------------------------------------------
    
  def prompt_action_confirm(self):
    self.confirm_prompt_result = None
    self.state = Menu.MENU_STATE_CONFIRM_PROMPT

  #----------------------------------------------------------------------------
    
  def get_text(self):
    return self.text

  #----------------------------------------------------------------------------
  
  ## Returns menu items in format: ( (column 1 row 1 text), (column 1 row 2 text), ...), ((column 2 row 1 text), ...) ).
  
  def get_items(self):
    return self.items

  #----------------------------------------------------------------------------
  
  ## Returns a selected menu item in format (row, column).
  
  def get_selected_item(self):
    return self.selected_item

  #----------------------------------------------------------------------------
  
  def process_inputs(self, input_list):
    if self.menu_left:
      self.menu_left = False
      self.state = Menu.MENU_STATE_SELECTING
      
      for action_code in self.action_keys_previous_state:
        self.action_keys_previous_state[action_code] = True
        
      return
    
    actions_processed = []
    actions_pressed = []
    
    for action in input_list:
      action_code = action[1]
      
      if not self.action_keys_previous_state[action_code]:
        # the following condition disallows ACTION_BOMB and ACTION_BOMB_DOUBLE to be in the list at the same time => causes trouble
        if (not (action_code in actions_pressed) and not(
          (action_code == PlayerKeyMaps.ACTION_BOMB and PlayerKeyMaps.ACTION_BOMB_DOUBLE in actions_pressed) or
          (action_code == PlayerKeyMaps.ACTION_BOMB_DOUBLE and PlayerKeyMaps.ACTION_BOMB in actions_pressed) )):
          actions_pressed.append(action_code)
    
      actions_processed.append(action_code)
    
    for action_code in self.action_keys_previous_state:
      self.action_keys_previous_state[action_code] = False
      
    for action_code in actions_processed:
      self.action_keys_previous_state[action_code] = True
    
    for action in actions_pressed:
      self.action_pressed(action)
  
  #----------------------------------------------------------------------------
   
  def mouse_went_over_item(self, item_coordinates):
    self.selected_item = item_coordinates

  #----------------------------------------------------------------------------
     
  ## Handles mouse button events in the menu.
     
  def mouse_button_pressed(self, button_number):
    if button_number == 0:       # left
      self.action_pressed(PlayerKeyMaps.ACTION_BOMB)
    elif button_number == 1:     # right
      self.action_pressed(PlayerKeyMaps.ACTION_SPECIAL)
    elif button_number == 3:     # up
      self.scroll(True)
    elif button_number == 4:     # down
      self.scroll(False)

  #----------------------------------------------------------------------------
    
  def scroll(self, up):
    if up:
      if self.scroll_position > 0:
        self.scroll_position -= 1
        self.action_pressed(PlayerKeyMaps.ACTION_UP)
    else:   # down
      rows = len(self.items[self.selected_item[1]])  
      maximum_row = rows - Menu.MENU_MAX_ITEMS_VISIBLE
      
      if self.scroll_position < maximum_row:
        self.scroll_position += 1
        self.action_pressed(PlayerKeyMaps.ACTION_DOWN)

  #----------------------------------------------------------------------------
    
  ## Should be called when the menu is being left.
     
  def leaving(self):
    self.menu_left = True
    self.confirm_prompt_result = None
    self.sound_player.play_sound_event(SoundPlayer.SOUND_EVENT_CONFIRM)

  #----------------------------------------------------------------------------
     
  ## Prompts confirmation of given menu item if it has been selected.
     
  def prompt_if_needed(self, menu_item_coordinates):
    if self.state == Menu.MENU_STATE_CONFIRM and (self.confirm_prompt_result == None or self.confirm_prompt_result == False) and self.selected_item == menu_item_coordinates:
      self.prompt_action_confirm()

  #----------------------------------------------------------------------------
     
  ## Is called once for every action key press (not each frame, which is
  #  not good for menus). This can be overridden.
  
  def action_pressed(self, action):
    old_selected_item = self.selected_item
    
    if self.state == Menu.MENU_STATE_CONFIRM_PROMPT:
      if action == PlayerKeyMaps.ACTION_BOMB or action == PlayerKeyMaps.ACTION_BOMB_DOUBLE:
        self.confirm_prompt_result = True
        self.state = Menu.MENU_STATE_CONFIRM
      else:
        self.confirm_prompt_result = False
        self.state = Menu.MENU_STATE_SELECTING
    else:
      if action == PlayerKeyMaps.ACTION_UP:
        self.selected_item = (max(0,self.selected_item[0] - 1),self.selected_item[1])
      elif action == PlayerKeyMaps.ACTION_DOWN:
        self.selected_item = (min(len(self.items[self.selected_item[1]]) - 1,self.selected_item[0] + 1),self.selected_item[1])
      elif action == PlayerKeyMaps.ACTION_LEFT:
        new_column = max(0,self.selected_item[1] - 1)
        self.selected_item = (min(len(self.items[new_column]) - 1,self.selected_item[0]),new_column)
      elif action == PlayerKeyMaps.ACTION_RIGHT:
        new_column = min(len(self.items) - 1,self.selected_item[1] + 1)
        self.selected_item = (min(len(self.items[new_column]) - 1,self.selected_item[0]),new_column)
      elif action == PlayerKeyMaps.ACTION_BOMB or action == PlayerKeyMaps.ACTION_BOMB_DOUBLE:
        self.state = Menu.MENU_STATE_CONFIRM
      elif action == PlayerKeyMaps.ACTION_SPECIAL:
        self.state = Menu.MENU_STATE_CANCEL
      
    if self.selected_item[0] >= self.scroll_position + Menu.MENU_MAX_ITEMS_VISIBLE:
      self.scroll_position += 1
    elif self.selected_item[0] < self.scroll_position:
      self.scroll_position -= 1
      
    if self.selected_item != old_selected_item:
      self.sound_player.play_sound_event(SoundPlayer.SOUND_EVENT_CLICK)
    
#==============================================================================

class MainMenu(Menu):

  #----------------------------------------------------------------------------

  def __init__(self, sound_player):
    super(MainMenu,self).__init__(sound_player)
    
    self.items = [(
      "let's play!",
      "tweak some stuff",
      "what's this about",
      "run away!")]

  #----------------------------------------------------------------------------
    
  def action_pressed(self, action):
    super(MainMenu,self).action_pressed(action)
    self.prompt_if_needed((3,0))

#==============================================================================

class ResultMenu(Menu):

  SEPARATOR = "__________________________________________________"

  #----------------------------------------------------------------------------

  def __init__(self, sound_player):
    super(ResultMenu,self).__init__(sound_player)
    
    self.items = [["I get it"]]

  #----------------------------------------------------------------------------

  def _format_player_cel(self, player):
    return (
        Renderer.colored_color_name(player.get_number()) + " (" +
        Renderer.colored_text(player.get_team_number(),str(player.get_team_number() + 1)) + "): " +
        str(player.get_kills()) + "/" + str(player.get_wins())
        )

  #----------------------------------------------------------------------------

  def _format_winning_teams(self, players):
    announcement_text =""

    win_maximum = 0
    winner_team_numbers = []
    
    teams = defaultdict(int) # { team_number : number_of_wins }

    for player in players:
      teams[player.get_team_number()] += 1

    for team_number, team_wins in teams.items():
      if team_wins == win_maximum:
        winner_team_numbers.append(team_number)
      elif team_wins > win_maximum:
        win_maximum = team_wins
        winner_team_numbers = [team_number]

    if len(winner_team_numbers) == 1:
      announcement_text = "Winner team is " + Renderer.colored_color_name(winner_team_numbers[0]) + "!"
    else:
      announcement_text = "Winners teams are: "
      announcement_text += ", ".join(map(lambda team_no: Renderer.colored_color_name(team_no),
                                     winner_team_numbers))
      announcement_text += "!"
    
    return announcement_text

  #----------------------------------------------------------------------------

  def _format_player_stats(self, players):
    announcement_text = ""
    row = 0
    column = 0
    # decide how many columns for different numbers of players will the table have
    columns_by_player_count = (1,2,3,2,3,3,4,4,3,5)
    table_columns = columns_by_player_count[len(players) - 1]
    
    for player in players:

      announcement_text += self._format_player_cel(player)
      
      column += 1
      
      if column >= table_columns:
        column = 0
        row += 1
        announcement_text += "\n"
      else:
        announcement_text += "     "
    
    return announcement_text

  #----------------------------------------------------------------------------

  def set_results(self, players):
    self.text = self._format_winning_teams(players)

    self.text += "\n" + ResultMenu.SEPARATOR + "\n"

    self.text += self._format_player_stats(players) 
      
    self.text += "\n" + ResultMenu.SEPARATOR

#==============================================================================
    
class PlayMenu(Menu):

  #----------------------------------------------------------------------------

  def __init__(self,sound_player):
    super(PlayMenu,self).__init__(sound_player)
    self.items = [("resume","to main menu")]

  #----------------------------------------------------------------------------
  
  def action_pressed(self, action):
    super(PlayMenu,self).action_pressed(action)
    self.prompt_if_needed((1,0))

#==============================================================================
      
class SettingsMenu(Menu):
  COLOR_ON = "^#1DF53A"
  COLOR_OFF = "^#F51111"

  #----------------------------------------------------------------------------
  
  def __init__(self, sound_player, settings, game):
    super(SettingsMenu,self).__init__(sound_player)
    self.settings = settings
    self.game = game
    self.update_items()  

  #----------------------------------------------------------------------------
   
  def bool_to_str(self, bool_value):
    return SettingsMenu.COLOR_ON + "on" if bool_value else SettingsMenu.COLOR_OFF + "off"

  #----------------------------------------------------------------------------
    
  def update_items(self):
    self.items = [(
      "sound volume: " + (SettingsMenu.COLOR_ON if self.settings.sound_is_on() else SettingsMenu.COLOR_OFF) + str(int(self.settings.sound_volume * 10) * 10) + " %",
      "music volume: " + (SettingsMenu.COLOR_ON if self.settings.music_is_on() > 0.0 else SettingsMenu.COLOR_OFF) + str(int(self.settings.music_volume * 10) * 10) + " %",
      "screen resolution: " + str(self.settings.screen_resolution[0]) + " x " + str(self.settings.screen_resolution[1]),
      "fullscreen: " + self.bool_to_str(self.settings.fullscreen),
      "allow control by mouse: " + self.bool_to_str(self.settings.control_by_mouse),
      "configure controls",
      "complete reset",
      "back"
      )]    

  #----------------------------------------------------------------------------
    
  def action_pressed(self, action):
    super(SettingsMenu,self).action_pressed(action)

    self.prompt_if_needed((6,0))
    
    mouse_control_selected = False
    fullscreen_selected = False
    
    if self.state == Menu.MENU_STATE_SELECTING:
      if action == PlayerKeyMaps.ACTION_RIGHT:
        if self.selected_item == (0,0):
          self.settings.sound_volume = min(1.0,self.settings.sound_volume + 0.1)
          self.game.apply_sound_settings()
          self.game.save_settings()
        elif self.selected_item == (1,0):
          self.settings.music_volume = min(1.0,self.settings.music_volume + 0.1)
          self.game.apply_sound_settings()
          self.game.save_settings()
        elif self.selected_item == (2,0):
          self.settings.screen_resolution = Settings.POSSIBLE_SCREEN_RESOLUTIONS[(self.settings.current_resolution_index() + 1) % len(Settings.POSSIBLE_SCREEN_RESOLUTIONS)]      
          self.game.apply_screen_settings()
          self.game.save_settings()
      elif action == PlayerKeyMaps.ACTION_LEFT:
        if self.selected_item == (0,0):
          self.settings.sound_volume = max(0.0,self.settings.sound_volume - 0.1)
          self.game.apply_sound_settings()
          self.game.save_settings()
        elif self.selected_item == (1,0):
          self.settings.music_volume = max(0.0,self.settings.music_volume - 0.1)
          self.game.apply_sound_settings()
          self.game.save_settings()
        elif self.selected_item == (2,0):
          self.settings.screen_resolution = Settings.POSSIBLE_SCREEN_RESOLUTIONS[(self.settings.current_resolution_index() - 1) % len(Settings.POSSIBLE_SCREEN_RESOLUTIONS)]
          self.game.apply_screen_settings()
          self.game.save_settings()
    elif self.state == Menu.MENU_STATE_CONFIRM:
      if self.selected_item == (6,0):
        
        debug_log("resetting settings")
        
        self.settings.reset()
        self.game.save_settings()
        self.game.apply_sound_settings()
        self.game.apply_screen_settings()
        self.game.apply_other_settings()
        self.confirm_prompt_result = None
        self.state = Menu.MENU_STATE_SELECTING    
      elif self.selected_item == (3,0):
        fullscreen_selected = True
        self.state = Menu.MENU_STATE_SELECTING  
      elif self.selected_item == (4,0):
        mouse_control_selected = True
        self.state = Menu.MENU_STATE_SELECTING  
      elif self.selected_item != (7,0) and self.selected_item != (5,0):
        self.state = Menu.MENU_STATE_SELECTING  
      
    if mouse_control_selected:
      self.settings.control_by_mouse = not self.settings.control_by_mouse
      self.game.apply_other_settings()
      self.game.save_settings()
      self.state = Menu.MENU_STATE_SELECTING
      
    if fullscreen_selected:
      self.settings.fullscreen = not self.settings.fullscreen
      self.game.apply_screen_settings()
      self.game.save_settings()
      self.state = Menu.MENU_STATE_SELECTING

    self.update_items()

#==============================================================================
          
class ControlsMenu(Menu):

  #----------------------------------------------------------------------------

  def __init__(self, sound_player, player_key_maps, game):
    super(ControlsMenu,self).__init__(sound_player)
    self.player_key_maps = player_key_maps
    self.game = game
    self.waiting_for_key = None     # if not None, this contains a tuple (player number, action) of action that is currently being remapped
    self.wait_for_release = False   # used to wait for keys release before new key map is captured

    self.update_items()

  #----------------------------------------------------------------------------

  def color_key_string(self, key_string):
    return "^#38A8F2" + key_string if key_string != "none" else "^#E83535" + key_string

  #----------------------------------------------------------------------------
    
  def update_items(self):
    self.items = [["go back"]]
    
    prompt_string = "press some key"
    
    for i in xrange(Game.NUMBER_OF_CONTROLLED_PLAYERS):
      player_string = "p " + str(i + 1)
      
      player_maps = self.player_key_maps.get_players_key_mapping(i)

      for action in player_maps:
        item_string = player_string + " " + PlayerKeyMaps.ACTION_NAMES[action] + ": "
        
        if self.waiting_for_key == (i,action):
          item_string += prompt_string
        else:
          item_string += self.color_key_string(PlayerKeyMaps.key_to_string(player_maps[action]))
        
        self.items[0] += [item_string]
      
    # add menu item
    item_string = "open menu: "
    
    if self.waiting_for_key != None and self.waiting_for_key[1] == PlayerKeyMaps.ACTION_MENU:
      item_string += prompt_string
    else:
      item_string += self.color_key_string(PlayerKeyMaps.key_to_string(self.player_key_maps.get_menu_key_map()))
      
    self.items[0] += [item_string]

  #----------------------------------------------------------------------------

  ## This should be called periodically when the menu is active. It will
  #  take care of catching pressed keys if waiting for key remap.

  def update(self, player_key_maps):
    if self.waiting_for_key != None:
      keys_pressed = list(pygame.key.get_pressed()) 
      
      key_pressed = None
      
      mouse_actions = player_key_maps.get_current_mouse_control_states()     
      
      if len(mouse_actions) > 0:
        key_pressed = mouse_actions[0]
        
      for i in xrange(len(keys_pressed)):      # find pressed key
        if not (i in (pygame.K_NUMLOCK,pygame.K_CAPSLOCK,pygame.K_SCROLLOCK,322)) and keys_pressed[i]:
          key_pressed = i
          break
        
      if self.wait_for_release:
        if key_pressed == None:
          self.wait_for_release = False
      else:
         if key_pressed != None:
           
           debug_log("new key mapping")
           
           self.player_key_maps.set_one_key_map(key_pressed,self.waiting_for_key[0],self.waiting_for_key[1])
           self.waiting_for_key = None
           self.state = Menu.MENU_STATE_SELECTING
           self.game.save_settings()
           
           for item in self.action_keys_previous_state:
             self.action_keys_previous_state[item] = True
    
    self.update_items()

  #----------------------------------------------------------------------------

  def action_pressed(self, action):
    super(ControlsMenu,self).action_pressed(action)
    
    if self.waiting_for_key != None:
      self.waiting_for_key = None
      self.state = Menu.MENU_STATE_SELECTING
    elif action == PlayerKeyMaps.ACTION_BOMB and self.selected_item[0] > 0:
      # new key map will be captured
      helper_index = self.selected_item[0] - 1
      
      if helper_index == Game.NUMBER_OF_CONTROLLED_PLAYERS * 6:   # 6 controls for each player, then menu item follows
        self.waiting_for_key = (-1,PlayerKeyMaps.ACTION_MENU)
      else:
        action_index = helper_index % 6
        
        helper_array = (PlayerKeyMaps.ACTION_UP,PlayerKeyMaps.ACTION_RIGHT,PlayerKeyMaps.ACTION_DOWN,PlayerKeyMaps.ACTION_LEFT,PlayerKeyMaps.ACTION_BOMB,PlayerKeyMaps.ACTION_SPECIAL)
        helper_action = helper_array[action_index]
        
        self.waiting_for_key = (helper_index / 6,helper_action)
      
      self.wait_for_release = True
      
      self.state = Menu.MENU_STATE_SELECTING
      
    self.update_items()

#==============================================================================
        
class AboutMenu(Menu):

  #----------------------------------------------------------------------------

  def __init__(self,sound_player):
    super(AboutMenu,self).__init__(sound_player) 
    self.text = ("^#2E44BFBombman^#FFFFFF - free Bomberman clone, ^#4EF259version " + Game.VERSION_STR + "\n"
                 "Miloslav \"tastyfish\" Ciz, 2016\n\n"
                 "This game is free software, published under CC0 1.0.\n")
    self.items = [["ok, nice, back"]]

#==============================================================================
    
class MapSelectMenu(Menu):

  #----------------------------------------------------------------------------

  def __init__(self,sound_player):
    super(MapSelectMenu,self).__init__(sound_player)
    self.text = "Now select a map."
    self.map_filenames = []
    self.update_items()

  #----------------------------------------------------------------------------
    
  def update_items(self):
    self.map_filenames = sorted([filename for filename in os.listdir(Game.MAP_PATH) if os.path.isfile(os.path.join(Game.MAP_PATH,filename))])

    special_color = (100,100,255)

    self.items = [["^" + Renderer.rgb_to_html_notation(special_color) + "pick random","^" + Renderer.rgb_to_html_notation(special_color) + "each game random"]]

    for filename in self.map_filenames:
      self.items[0].append(filename)

  #----------------------------------------------------------------------------
    
  def random_was_selected(self):
    return self.selected_item[0] == 1

  #----------------------------------------------------------------------------
    
  def show_map_preview(self):
    return self.selected_item[0] != 0 and self.selected_item[0] != 1

  #----------------------------------------------------------------------------
    
  def get_random_map_name(self):
    return random.choice(self.map_filenames)

  #----------------------------------------------------------------------------
    
  def get_selected_map_name(self):
    if self.selected_item[0] == 0:                # pick random
      return random.choice(self.map_filenames)
    
    try:
      index = self.selected_item[0] - 2
      
      if index < 0:
        return ""
      
      return self.map_filenames[index]
    except IndexError:
      return ""

#==============================================================================
    
class PlaySetupMenu(Menu):

  #----------------------------------------------------------------------------

  def __init__(self, sound_player, play_setup):
    super(PlaySetupMenu,self).__init__(sound_player)
    self.selected_item = (0,1)
    self.play_setup = play_setup
    self.update_items()

  #----------------------------------------------------------------------------
    
  def update_items(self):
    self.items = [[],[],["games: " + str(self.play_setup.get_number_of_games())]]
    
    dark_grey = (50,50,50)
      
    self.items[0].append("back")
    self.items[1].append("next")
         
    for i in xrange(10):
      slot_color = Renderer.COLOR_RGB_VALUES[i] if i != Game.COLOR_BLACK else dark_grey  # black with black border not visible, use dark grey
      
      self.items[0].append(Renderer.colored_text(i,str(i + 1)) + ": ")
      
      slot = self.play_setup.get_slots()[i]
      
      if slot == None:
        self.items[0][-1] += "-"
        self.items[1].append("-")
      else:
        team_color = Renderer.COLOR_RGB_VALUES[slot[1]] if slot[1] != Game.COLOR_BLACK else dark_grey
        self.items[0][-1] += ("player " + str(slot[0] + 1)) if slot[0] >= 0 else "AI"
        self.items[1].append(Renderer.colored_text(slot[1],str(slot[1] + 1)))    # team number

  #----------------------------------------------------------------------------
 
  def action_pressed(self, action):
    super(PlaySetupMenu,self).action_pressed(action)
    
    if action == PlayerKeyMaps.ACTION_UP:
      if self.selected_item == (0,2):
        self.play_setup.increase_number_of_games()  
        self.state = Menu.MENU_STATE_SELECTING
    elif action == PlayerKeyMaps.ACTION_DOWN:
      if self.selected_item == (0,2):
        self.play_setup.decrease_number_of_games()
        self.state = Menu.MENU_STATE_SELECTING
    elif self.state == Menu.MENU_STATE_CONFIRM:  
      if self.selected_item == (0,2):
        self.play_setup.increase_number_of_games()
        self.state = Menu.MENU_STATE_SELECTING
    
      if self.selected_item[0] > 0:  # override behaviour for confirm button
        slots = self.play_setup.get_slots()
        slot = slots[self.selected_item[0] - 1]
      
        if self.selected_item[1] == 0:
          # changing players
        
          if slot == None:
            new_value = -1
          else:
            new_value = slot[0] + 1
          
          slots[self.selected_item[0] - 1] = (new_value,slot[1] if slot != None else self.selected_item[0] - 1) if new_value <= 3 else None  
        else:
          # changing teams
        
          if slot != None:
            slots[self.selected_item[0] - 1] = (slot[0],(slot[1] + 1) % 10)
      
        self.state = Menu.MENU_STATE_SELECTING
      
    self.update_items()
 
#==============================================================================
      
class Renderer(object):
  COLOR_RGB_VALUES = [
    (210,210,210),           # white
    (10,10,10),              # black
    (255,0,0),               # red
    (0,0,255),               # blue
    (0,255,0),               # green
    (52,237,250),            # cyan
    (255,255,69),            # yellow
    (255,192,74),            # orange
    (168,127,56),            # brown
    (209,117,206)            # purple
    ]
    
  MAP_TILE_WIDTH = 50              ##< tile width in pixels
  MAP_TILE_HEIGHT = 45             ##< tile height in pixels
  MAP_TILE_HALF_WIDTH = MAP_TILE_WIDTH / 2
  MAP_TILE_HALF_HEIGHT = MAP_TILE_HEIGHT / 2

  PLAYER_SPRITE_CENTER = (30,80)   ##< player's feet (not geometrical) center of the sprite in pixels
  BOMB_SPRITE_CENTER = (22,33)
  SHADOW_SPRITE_CENTER = (25,22)

  MAP_BORDER_WIDTH = 37
  
  ANIMATION_EVENT_EXPLOSION = 0
  ANIMATION_EVENT_RIP = 1
  ANIMATION_EVENT_SKELETION = 2
  ANIMATION_EVENT_DISEASE_CLOUD = 3
  ANIMATION_EVENT_DIE = 4
  
  FONT_SMALL_SIZE = 12
  FONT_NORMAL_SIZE = 25
  MENU_LINE_SPACING = 10
  MENU_FONT_COLOR = (255,255,255)
  
  SCROLLBAR_RELATIVE_POSITION = (-200,-50)
  SCROLLBAR_HEIGHT = 300
  
  MENU_DESCRIPTION_Y_OFFSET = -80

  #----------------------------------------------------------------------------

  def __init__(self):
    self.update_screen_info()

    self.environment_images = {}
    
    self.preview_map_name = ""
    self.preview_map_image = None

    self.font_small = pygame.font.Font(os.path.join(Game.RESOURCE_PATH,"LibertySans.ttf"),Renderer.FONT_SMALL_SIZE)
    self.font_normal = pygame.font.Font(os.path.join(Game.RESOURCE_PATH,"LibertySans.ttf"),Renderer.FONT_NORMAL_SIZE)

    self.previous_mouse_coordinates = (-1,-1)

    pygame.mouse.set_visible(False)    # hide mouse cursor

    environment_names = ["env1","env2","env3","env4","env5","env6","env7"]

    for environment_name in environment_names:
      filename_floor = os.path.join(Game.RESOURCE_PATH,"tile_" + environment_name + "_floor.png")
      filename_block = os.path.join(Game.RESOURCE_PATH,"tile_" + environment_name + "_block.png")
      filename_wall = os.path.join(Game.RESOURCE_PATH,"tile_" + environment_name + "_wall.png")

      self.environment_images[environment_name] = (pygame.image.load(filename_floor),pygame.image.load(filename_block),pygame.image.load(filename_wall))

    self.prerendered_map = None     # keeps a reference to a map for which some parts have been prerendered
    self.prerendered_map_background = pygame.Surface((GameMap.MAP_WIDTH * Renderer.MAP_TILE_WIDTH + 2 * Renderer.MAP_BORDER_WIDTH,GameMap.MAP_HEIGHT * Renderer.MAP_TILE_HEIGHT + 2 * Renderer.MAP_BORDER_WIDTH))

    self.player_images = []         ##< player images in format [color index]["sprite name"] and [color index]["sprite name"][frame]

    for i in xrange(10):
      self.player_images.append({})
      
      for helper_string in ["up","right","down","left"]:
        self.player_images[-1][helper_string] =  self.color_surface(pygame.image.load(os.path.join(Game.RESOURCE_PATH,"player_" + helper_string + ".png")),i)
        
        string_index = "walk " + helper_string
      
        self.player_images[-1][string_index] = []
        self.player_images[-1][string_index].append(self.color_surface(pygame.image.load(os.path.join(Game.RESOURCE_PATH,"player_" + helper_string + "_walk1.png")),i))
        
        if helper_string == "up" or helper_string == "down":
          self.player_images[-1][string_index].append(self.color_surface(pygame.image.load(os.path.join(Game.RESOURCE_PATH,"player_" + helper_string + "_walk2.png")),i))
        else:
          self.player_images[-1][string_index].append(self.player_images[-1][helper_string])
        
        self.player_images[-1][string_index].append(self.color_surface(pygame.image.load(os.path.join(Game.RESOURCE_PATH,"player_" + helper_string + "_walk3.png")),i))
        self.player_images[-1][string_index].append(self.player_images[-1][string_index][0])
        
        string_index = "box " + helper_string
        self.player_images[-1][string_index] = self.color_surface(pygame.image.load(os.path.join(Game.RESOURCE_PATH,"player_" + helper_string + "_box.png")),i)
     
    self.bomb_images = []
    self.bomb_images.append(pygame.image.load(os.path.join(Game.RESOURCE_PATH,"bomb1.png")))
    self.bomb_images.append(pygame.image.load(os.path.join(Game.RESOURCE_PATH,"bomb2.png")))
    self.bomb_images.append(pygame.image.load(os.path.join(Game.RESOURCE_PATH,"bomb3.png")))
    self.bomb_images.append(self.bomb_images[0])
     
    # load flame images
    
    self.flame_images = []
    
    for i in [1,2]:
      helper_string = "flame" + str(i)
      
      self.flame_images.append({})
      self.flame_images[-1]["all"] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,helper_string + ".png"))
      self.flame_images[-1]["horizontal"] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,helper_string + "_horizontal.png"))
      self.flame_images[-1]["vertical"] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,helper_string + "_vertical.png"))
      self.flame_images[-1]["left"] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,helper_string + "_left.png"))
      self.flame_images[-1]["right"] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,helper_string + "_right.png"))
      self.flame_images[-1]["up"] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,helper_string + "_up.png"))
      self.flame_images[-1]["down"] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,helper_string + "_down.png"))
      
    # load item images
    
    self.item_images = {}
    
    self.item_images[GameMap.ITEM_BOMB] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"item_bomb.png"))
    self.item_images[GameMap.ITEM_FLAME] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"item_flame.png"))
    self.item_images[GameMap.ITEM_SUPERFLAME] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"item_superflame.png"))
    self.item_images[GameMap.ITEM_SPEEDUP] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"item_speedup.png"))
    self.item_images[GameMap.ITEM_DISEASE] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"item_disease.png"))
    self.item_images[GameMap.ITEM_RANDOM] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"item_random.png"))
    self.item_images[GameMap.ITEM_SPRING] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"item_spring.png"))
    self.item_images[GameMap.ITEM_SHOE] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"item_shoe.png"))
    self.item_images[GameMap.ITEM_MULTIBOMB] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"item_multibomb.png"))
    self.item_images[GameMap.ITEM_RANDOM] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"item_random.png"))
    self.item_images[GameMap.ITEM_BOXING_GLOVE] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"item_boxing_glove.png"))
    self.item_images[GameMap.ITEM_DETONATOR] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"item_detonator.png"))
    self.item_images[GameMap.ITEM_THROWING_GLOVE] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"item_throwing_glove.png"))
      
    # load/make gui images
    
    self.gui_images = {}
    self.gui_images["info board"] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"gui_info_board.png"))   
    self.gui_images["arrow up"] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"gui_arrow_up.png"))   
    self.gui_images["arrow down"] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"gui_arrow_down.png"))   
    self.gui_images["seeker"] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"gui_seeker.png"))
    self.gui_images["cursor"] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"gui_cursor.png"))   
    self.gui_images["prompt"] = self.render_text(self.font_normal,"You sure?",(255,255,255))
    self.gui_images["version"] = self.render_text(self.font_small,"v " + Game.VERSION_STR,(0,100,0))
    
    self.player_info_board_images = [None for i in xrange(10)]  # up to date infoboard image for each player

    self.gui_images["out"] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"gui_out.png"))   
     
    self.gui_images["countdown"] = {}
    
    self.gui_images["countdown"][1] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"gui_countdown_1.png"))
    self.gui_images["countdown"][2] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"gui_countdown_2.png"))
    self.gui_images["countdown"][3] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"gui_countdown_3.png"))
    
    self.menu_background_image = None  ##< only loaded when in menu
    self.menu_item_images = None       ##< images of menu items, only loaded when in menu
 
    # load other images
    
    self.other_images = {}
    
    self.other_images["shadow"] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"other_shadow.png"))
    self.other_images["spring"] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"other_spring.png"))
    self.other_images["antena"] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"other_antena.png"))
     
    self.other_images["disease"] = []
    self.other_images["disease"].append(pygame.image.load(os.path.join(Game.RESOURCE_PATH,"other_disease1.png")))
    self.other_images["disease"].append(pygame.image.load(os.path.join(Game.RESOURCE_PATH,"other_disease2.png")))    
          
    # load icon images
    
    self.icon_images = {}
    self.icon_images[GameMap.ITEM_BOMB] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"icon_bomb.png"))
    self.icon_images[GameMap.ITEM_FLAME] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"icon_flame.png"))
    self.icon_images[GameMap.ITEM_SPEEDUP] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"icon_speedup.png"))
    self.icon_images[GameMap.ITEM_SHOE] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"icon_kicking_shoe.png"))
    self.icon_images[GameMap.ITEM_BOXING_GLOVE] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"icon_boxing_glove.png"))
    self.icon_images[GameMap.ITEM_THROWING_GLOVE] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"icon_throwing_glove.png"))
    self.icon_images[GameMap.ITEM_SPRING] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"icon_spring.png"))
    self.icon_images[GameMap.ITEM_MULTIBOMB] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"icon_multibomb.png"))
    self.icon_images[GameMap.ITEM_DISEASE] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"icon_disease.png"))
    self.icon_images[GameMap.ITEM_DETONATOR] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"icon_detonator.png"))
    self.icon_images["etc"] = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"icon_etc.png"))
    
    # load animations
    
    self.animations = {}
    self.animations[Renderer.ANIMATION_EVENT_EXPLOSION] = Animation(os.path.join(Game.RESOURCE_PATH,"animation_explosion"),1,10,".png",7)
    self.animations[Renderer.ANIMATION_EVENT_RIP] = Animation(os.path.join(Game.RESOURCE_PATH,"animation_rip"),1,1,".png",0.3)
    self.animations[Renderer.ANIMATION_EVENT_SKELETION] = Animation(os.path.join(Game.RESOURCE_PATH,"animation_skeleton"),1,10,".png",7)
    self.animations[Renderer.ANIMATION_EVENT_DISEASE_CLOUD] = Animation(os.path.join(Game.RESOURCE_PATH,"animation_disease"),1,6,".png",5)
    self.animations[Renderer.ANIMATION_EVENT_DIE] = Animation(os.path.join(Game.RESOURCE_PATH,"animation_die"),1,7,".png",7)

    self.party_circles = []     ##< holds info about party cheat circles, list of tuples in format (coords,radius,color,phase,speed)
    self.party_circles.append(((-180,110),40,(255,100,50),0.0,1.0))
    self.party_circles.append(((160,70),32,(100,200,150),1.4,1.5))
    self.party_circles.append(((40,-150),65,(150,100,170),2.0,0.7))
    self.party_circles.append(((-170,-92),80,(200,200,32),3.2,1.3))
    self.party_circles.append(((50,110),63,(10,180,230),0.1,1.8))
    self.party_circles.append(((205,-130),72,(180,150,190),0.5,2.0))
    
    self.party_players = []     ##< holds info about party cheat players, list of tuples in format (coords,color index,millisecond delay, rotate right)
    self.party_players.append(((-230,80),0,0,True))
    self.party_players.append(((180,10),2,220,False))
    self.party_players.append(((90,-150),4,880,True))
    self.party_players.append(((-190,-95),6,320,False))
    self.party_players.append(((-40,110),8,50,True))
    
    self.party_bombs = []       ##< holds info about party bombs, list of lists in format [x,y,increment x,increment y]
    self.party_bombs.append([10,30,1,1])
    self.party_bombs.append([700,200,1,-1])
    self.party_bombs.append([512,512,-1,1])
    self.party_bombs.append([1024,20,-1,-1])
    self.party_bombs.append([900,300,1,1])
    self.party_bombs.append([30,700,1,1])
    self.party_bombs.append([405,530,1,-1])
    self.party_bombs.append([250,130,-1,-1])

  #----------------------------------------------------------------------------

  def update_screen_info(self):
    self.screen_resolution = Renderer.get_screen_size()
    self.screen_center = (self.screen_resolution[0] / 2,self.screen_resolution[1] / 2)
    self.map_render_location = Renderer.get_map_render_position()

  #----------------------------------------------------------------------------
  
  ## Converts (r,g,b) tuple to html #rrggbb notation.

  @staticmethod
  def rgb_to_html_notation(rgb_color):
    return "#" + hex(rgb_color[0])[2:].zfill(2) + hex(rgb_color[1])[2:].zfill(2) + hex(rgb_color[2])[2:].zfill(2)

  #----------------------------------------------------------------------------
     
  @staticmethod
  def colored_text(color_index, text, end_with_white=True):
    return "^" + Renderer.rgb_to_html_notation(Renderer.lighten_color(Renderer.COLOR_RGB_VALUES[color_index],75)) + text + "^#FFFFFF"

  #----------------------------------------------------------------------------
    
  @staticmethod
  def colored_color_name(color_index, end_with_white=True):
    return Renderer.colored_text(color_index,Game.COLOR_NAMES[color_index])

  #----------------------------------------------------------------------------
  
  ## Returns colored image from another image (replaces red color with given color). This method is slow. Color is (r,g,b) tuple of 0 - 1 floats.

  def color_surface(self, surface, color_number):
    result = surface.copy()
    
    # change all red pixels to specified color
    for j in xrange(result.get_size()[1]):
      for i in xrange(result.get_size()[0]):
        pixel_color = result.get_at((i,j))
        
        if pixel_color.r == 255 and pixel_color.g == 0 and pixel_color.b == 0:
          pixel_color.r = Renderer.COLOR_RGB_VALUES[color_number][0]
          pixel_color.g = Renderer.COLOR_RGB_VALUES[color_number][1]
          pixel_color.b = Renderer.COLOR_RGB_VALUES[color_number][2]
          result.set_at((i,j),pixel_color)

    return result

  #----------------------------------------------------------------------------

  def tile_position_to_pixel_position(self, tile_position,center=(0,0)):
    return (int(float(tile_position[0]) * Renderer.MAP_TILE_WIDTH) - center[0],int(float(tile_position[1]) * Renderer.MAP_TILE_HEIGHT) - center[1])

  #----------------------------------------------------------------------------

  @staticmethod
  def get_screen_size():
    display = pygame.display.get_surface()
    
    return display.get_size() if display != None else (0,0)

  #----------------------------------------------------------------------------

  @staticmethod  
  def get_map_render_position(): 
    screen_size = Renderer.get_screen_size()
    return ((screen_size[0] - Renderer.MAP_BORDER_WIDTH * 2 - Renderer.MAP_TILE_WIDTH * GameMap.MAP_WIDTH) / 2,(screen_size[1] - Renderer.MAP_BORDER_WIDTH * 2 - Renderer.MAP_TILE_HEIGHT * GameMap.MAP_HEIGHT - 50) / 2)  

  #----------------------------------------------------------------------------
    
  @staticmethod
  def map_position_to_pixel_position(map_position, offset = (0,0)):
    map_render_location = Renderer.get_map_render_position()
    return (map_render_location[0] + int(map_position[0] * Renderer.MAP_TILE_WIDTH) + Renderer.MAP_BORDER_WIDTH + offset[0],map_render_location[1] + int(map_position[1] * Renderer.MAP_TILE_HEIGHT) + Renderer.MAP_BORDER_WIDTH + offset[1])
    
  def set_resolution(self, new_resolution):
    self.screen_resolution = new_resolution

  #----------------------------------------------------------------------------

  @staticmethod
  def darken_color(color, by_how_may):
    r = max(color[0] - by_how_may,0)
    g = max(color[1] - by_how_may,0)
    b = max(color[2] - by_how_may,0)
    return (r,g,b)

  #----------------------------------------------------------------------------

  @staticmethod
  def lighten_color(color, by_how_may):
    r = min(color[0] + by_how_may,255)
    g = min(color[1] + by_how_may,255)
    b = min(color[2] + by_how_may,255)
    return (r,g,b)

  #----------------------------------------------------------------------------

  def __render_info_board_item_row(self, x, y, limit, item_type, player, board_image):   
    item_count = 20 if item_type == GameMap.ITEM_FLAME and player.get_item_count(GameMap.ITEM_SUPERFLAME) >= 1 else player.get_item_count(item_type)
   
    for i in xrange(item_count):
      if i > limit:
        break
        
      image_to_draw = self.icon_images[item_type]
        
      if i == limit and player.get_item_count(item_type) > limit + 1:
        image_to_draw = self.icon_images["etc"]
        
      board_image.blit(image_to_draw,(x,y))
      x += self.icon_images[item_type].get_size()[0]    

  #----------------------------------------------------------------------------

  ## Updates info board images in self.player_info_board_images. This should be called each frame, as
  #  rerendering is done only when needed.

  def update_info_boards(self, players):
    for i in xrange(10):      # for each player number
      update_needed = False
      
      if self.player_info_board_images[i] == None:
        self.player_info_board_images[i] = self.gui_images["info board"].copy()
        update_needed = True
      
      player = None
      
      for one_player in players:
        if one_player.get_number() == i:
          player = one_player
          break
      
      if player == None:
        continue
      
      if player.info_board_needs_update():
        update_needed = True
      
      if not update_needed or player == None:
        continue
      
      # rerendering needed here
      
      debug_log("updating info board " + str(i))
      
      board_image = self.player_info_board_images[i]
      
      board_image.blit(self.gui_images["info board"],(0,0))
      board_image.blit(self.font_small.render(str(player.get_kills()),True,(0,0,0)),(45,0))
      board_image.blit(self.font_small.render(str(player.get_wins()),True,(0,0,0)),(65,0))
      board_image.blit(self.font_small.render(Game.COLOR_NAMES[i],True,Renderer.darken_color(Renderer.COLOR_RGB_VALUES[i],100)),(4,2))
      
      if player.is_dead():
        board_image.blit(self.gui_images["out"],(15,34))
        continue
      
      # render items

      x = 5
      dy = 12

      self.__render_info_board_item_row(x,20,5,GameMap.ITEM_BOMB,player,board_image)
      self.__render_info_board_item_row(x,20 + dy,5,GameMap.ITEM_FLAME,player,board_image)
      self.__render_info_board_item_row(x,20 + 2 * dy,9,GameMap.ITEM_SPEEDUP,player,board_image)

      y = 20 + 3 * dy

      items_to_check = [
        GameMap.ITEM_SHOE,
        GameMap.ITEM_BOXING_GLOVE,
        GameMap.ITEM_THROWING_GLOVE,
        GameMap.ITEM_SPRING,
        GameMap.ITEM_MULTIBOMB,
        GameMap.ITEM_DETONATOR,
        GameMap.ITEM_DISEASE]
      
      for item in items_to_check:
        if player.get_item_count(item) or item == GameMap.ITEM_DISEASE and player.get_disease() != Player.DISEASE_NONE:
          board_image.blit(self.icon_images[item],(x,y))
          x += self.icon_images[item].get_size()[0] + 1
 
  #----------------------------------------------------------------------------

  def process_animation_events(self, animation_event_list):
    for animation_event in animation_event_list:
      self.animations[animation_event[0]].play(animation_event[1])

  #----------------------------------------------------------------------------

  ## Renders text with outline, line breaks, formatting, etc.

  def render_text(self, font, text_to_render, color, outline_color = (0,0,0), center = False):
    text_lines = text_to_render.split("\n")
    rendered_lines = []
    
    width = height = 0
    
    first_line = True
    
    for text_line in text_lines:
      line = text_line.lstrip().rstrip()
      
      if len(line) == 0:
        continue
      
      line_without_format = re.sub(r"\^.......","",line)     # remove all the markup in format ^#dddddd

      new_rendered_line = pygame.Surface(font.size(line_without_format),flags=pygame.SRCALPHA)
      
      x = 0
      first = True
      starts_with_format = line[0] == "^"
 
      for subline in line.split("^"):
        if len(subline) == 0:
          continue
        
        has_format = starts_with_format if first else True
        first = False

        text_color = color
        
        if has_format:
          text_color = pygame.Color(subline[:7])
          subline = subline[7:]
        
        new_rendered_subline = font.render(subline,True,outline_color)   # create text with outline
        new_rendered_subline.blit(new_rendered_subline,(0,2))
        new_rendered_subline.blit(new_rendered_subline,(1,0))
        new_rendered_subline.blit(new_rendered_subline,(-1,0))
        new_rendered_subline.blit(font.render(subline,True,text_color),(0,1))      
        
        new_rendered_line.blit(new_rendered_subline,(x,0))
        
        x += new_rendered_subline.get_size()[0]
        
      rendered_lines.append(new_rendered_line)

      if not first_line:
        height += Renderer.MENU_LINE_SPACING
      
      first_line = False

      height += rendered_lines[-1].get_size()[1]
      width = max(width,rendered_lines[-1].get_size()[0])
    
    result = pygame.Surface((width,height),flags=pygame.SRCALPHA)
    
    y_step = font.get_height() + Renderer.MENU_LINE_SPACING
    
    for i in xrange(len(rendered_lines)):
      result.blit(rendered_lines[i],(0 if not center else (width - rendered_lines[i].get_size()[0]) / 2,i * y_step))
    
    return result

  #----------------------------------------------------------------------------

  ## Updates images in self.menu_item_images (only if needed).

  def update_menu_item_images(self, menu):
    if self.menu_item_images == None:
      self.menu_item_images = {}       # format: (row, column) : (item text, image)
    
    items = menu.get_items()

    item_coordinates = []
    
    for j in xrange(len(items)):
      for i in xrange(len(items[j])):
        item_coordinates.append((j,i))
    
    if len(menu.get_text()) != 0:
      item_coordinates.append(0)       # this is the menu description text

    for menu_coordinates in item_coordinates:
      update_needed = False
        
      if not (menu_coordinates in self.menu_item_images):
        update_needed = True
    
      if menu_coordinates == 0:
        item_text = menu.get_text()
        center_text = True
      else:
        item_text = items[menu_coordinates[0]][menu_coordinates[1]]
        center_text = False
      
      if not update_needed and item_text != self.menu_item_images[menu_coordinates][0]:
        update_needed = True        
          
      if update_needed:
        debug_log("updating menu item " + str(menu_coordinates))
          
        new_image = self.render_text(self.font_normal,item_text,Renderer.MENU_FONT_COLOR,center = center_text)
          
        # text itself
        new_image.blit(new_image,(0,1))
          
        self.menu_item_images[menu_coordinates] = (item_text,new_image)

  #----------------------------------------------------------------------------
    
  def render_menu(self, menu_to_render, game):
    result = pygame.Surface(self.screen_resolution)
    
    if self.menu_background_image == None:
      self.menu_background_image = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"gui_menu_background.png"))

    background_position = (self.screen_center[0] - self.menu_background_image.get_size()[0] / 2,self.screen_center[1] - self.menu_background_image.get_size()[1] / 2)
      
    profiler.measure_start("menu rend. backg.")
    result.blit(self.menu_background_image,background_position)
    profiler.measure_stop("menu rend. backg.")

    profiler.measure_start("menu rend. party")
    if game.cheat_is_active(Game.CHEAT_PARTY):
      for circle_info in self.party_circles:           # draw circles
        circle_coords = (self.screen_center[0] + circle_info[0][0],self.screen_center[1] + circle_info[0][1])     
        radius_coefficient = (math.sin(pygame.time.get_ticks() * circle_info[4] / 100.0 + circle_info[3]) + 1) / 2.0
        circle_radius = int(circle_info[1] * radius_coefficient)
        pygame.draw.circle(result,circle_info[2],circle_coords,circle_radius)
    
      for player_info in self.party_players:           # draw players
        player_coords = (self.screen_center[0] + player_info[0][0],self.screen_center[1] + player_info[0][1])     
        
        player_direction = (int((pygame.time.get_ticks() + player_info[2]) / 150)) % 4
        
        if not player_info[3]:
          player_direction = 3 - player_direction
        
        direction_string = ("up","right","down","left")[player_direction]
        
        if int(pygame.time.get_ticks() / 500) % 2 == 0:
          direction_string = "box " + direction_string
        
        result.blit(self.player_images[player_info[1]][direction_string],player_coords)
    
      for bomb_info in self.party_bombs:
        result.blit(self.bomb_images[0],(bomb_info[0],bomb_info[1]))
        bomb_info[0] += bomb_info[2]
        bomb_info[1] += bomb_info[3]
        
        if bomb_info[0] < 0:     # border collision, change direction
          bomb_info[2] = 1
        elif bomb_info[0] > self.screen_resolution[0] - 50:
          bomb_info[2] = -1
    
        if bomb_info[1] < 0:     # border collision, change direction
          bomb_info[3] = 1
        elif bomb_info[1] > self.screen_resolution[1] - 50:
          bomb_info[3] = -1
    
    profiler.measure_stop("menu rend. party")
    
    version_position = (3,1)
    
    result.blit(self.gui_images["version"],version_position)
    
    profiler.measure_start("menu rend. item update")
    self.update_menu_item_images(menu_to_render)
    
    # render menu description text
    
    y = self.screen_center[1] + Renderer.MENU_DESCRIPTION_Y_OFFSET
    
    if len(menu_to_render.get_text()) != 0:
      result.blit(self.menu_item_images[0][1],(self.screen_center[0] - self.menu_item_images[0][1].get_size()[0] / 2,y))    # menu description text image is at index 0      
      y += self.menu_item_images[0][1].get_size()[1] + Renderer.MENU_LINE_SPACING * 2
    
    menu_items = menu_to_render.get_items()
    
    columns = len(menu_items)   # how many columns there are
    
    column_x_space = 150
    
    if columns % 2 == 0:
      xs = [self.screen_center[0] + i * column_x_space - ((columns - 1) * column_x_space / 2) for i in xrange(columns)] # even number of columns
    else:
      xs = [self.screen_center[0] + (i - columns / 2) * column_x_space for i in xrange(columns)]
    
    selected_coordinates = menu_to_render.get_selected_item()
    
    items_y = y
    
    profiler.measure_stop("menu rend. item update")
    
    # render scrollbar if needed
    
    rows = 0
    
    for column in menu_items:
      rows = max(rows,len(column))

    if rows > Menu.MENU_MAX_ITEMS_VISIBLE:
      x = xs[0] + Renderer.SCROLLBAR_RELATIVE_POSITION[0]
      
      result.blit(self.gui_images["arrow up"],(x,items_y))
      result.blit(self.gui_images["arrow down"],(x,items_y + Renderer.SCROLLBAR_HEIGHT))
      
      scrollbar_position = int(items_y + selected_coordinates[0] / float(rows) * Renderer.SCROLLBAR_HEIGHT)
      result.blit(self.gui_images["seeker"],(x,scrollbar_position))
    
    mouse_coordinates = pygame.mouse.get_pos()
    
    # render items
    
    profiler.measure_start("menu rend. items")
    
    for j in xrange(len(menu_items)):
      y = items_y
      
      for i in xrange(min(Menu.MENU_MAX_ITEMS_VISIBLE,len(menu_items[j]) - menu_to_render.get_scroll_position())):
        item_image = self.menu_item_images[(j,i + menu_to_render.get_scroll_position())][1]

        x = xs[j] - item_image.get_size()[0] / 2
                
        if (i + menu_to_render.get_scroll_position(),j) == selected_coordinates:
          # item is selected
          scale = (8 + math.sin(pygame.time.get_ticks() / 40.0)) / 7.0    # make the pulsating effect
          item_image = pygame.transform.scale(item_image,(int(scale * item_image.get_size()[0]),int(scale * item_image.get_size()[1])))
          x = xs[j] - item_image.get_size()[0] / 2
          pygame.draw.rect(result,(255,0,0),pygame.Rect(x - 4,y - 2,item_image.get_size()[0] + 8,item_image.get_size()[1] + 4))
        
        result.blit(item_image,(x,y))
        
        # did mouse go over the item?
        
        if (not game.get_settings().control_by_mouse) and (self.previous_mouse_coordinates != mouse_coordinates) and (x <= mouse_coordinates[0] <= x + item_image.get_size()[0]) and (y <= mouse_coordinates[1] <= y + item_image.get_size()[1]):
          item_coordinates = (i + menu_to_render.get_scroll_position(),j)
          menu_to_render.mouse_went_over_item(item_coordinates)
       
        y += Renderer.FONT_NORMAL_SIZE + Renderer.MENU_LINE_SPACING
    
    profiler.measure_stop("menu rend. items")
    
    mouse_events = game.get_player_key_maps().get_mouse_button_events()
    
    for i in xrange(len(mouse_events)):
      if mouse_events[i]:
        menu_to_render.mouse_button_pressed(i)
    
    self.previous_mouse_coordinates = mouse_coordinates
    
    # render confirm dialog if prompting
    
    if menu_to_render.get_state() == Menu.MENU_STATE_CONFIRM_PROMPT:
      width = 120
      height = 80
      x = self.screen_center[0] - width / 2
      y = self.screen_center[1] - height / 2
      
      pygame.draw.rect(result,(0,0,0),pygame.Rect(x,y,width,height))
      pygame.draw.rect(result,(255,255,255),pygame.Rect(x,y,width,height),1)
      
      text_image = pygame.transform.rotate(self.gui_images["prompt"],math.sin(pygame.time.get_ticks() / 100) * 5)
      
      x = self.screen_center[0] - text_image.get_size()[0] / 2
      y = self.screen_center[1] - text_image.get_size()[1] / 2
      
      result.blit(text_image,(x,y))
    
    # map preview
    
    profiler.measure_start("menu rend. preview")
    
    if isinstance(menu_to_render,MapSelectMenu):       # also not too nice    
      if menu_to_render.show_map_preview():
        self.update_map_preview_image(menu_to_render.get_selected_map_name())
        result.blit(self.preview_map_image,(self.screen_center[0] + 180,items_y))
    
    profiler.measure_stop("menu rend. preview")
    
    # draw cursor only if control by mouse is not allowed - wouldn't make sense
    
    if not game.get_settings().control_by_mouse:
      result.blit(self.gui_images["cursor"],pygame.mouse.get_pos())
    
    return result

  #----------------------------------------------------------------------------

  def update_map_preview_image(self, map_filename):
    if map_filename == "":
      self.preview_map_name = ""
      self.preview_map_image = None
      return
    
    if self.preview_map_name != map_filename:
      debug_log("updating map preview of " + map_filename)
      
      self.preview_map_name = map_filename
      
      tile_size = 7
      tile_half_size = tile_size / 2
    
      map_info_border_size = 5
    
      self.preview_map_image = pygame.Surface((tile_size * GameMap.MAP_WIDTH,tile_size * GameMap.MAP_HEIGHT + map_info_border_size + Renderer.MAP_TILE_HEIGHT))
    
      with open(os.path.join(Game.MAP_PATH,map_filename)) as map_file:
        map_data = map_file.read()
        temp_map = GameMap(map_data,PlaySetup(),0,0)
        
        for y in xrange(GameMap.MAP_HEIGHT):
          for x in xrange(GameMap.MAP_WIDTH):
            tile = temp_map.get_tile_at((x,y))
            tile_kind = tile.kind
            
            pos_x = x * tile_size
            pos_y = y * tile_size
            
            tile_special_object = tile.special_object
            
            if tile_special_object == None: 
              if tile_kind == MapTile.TILE_BLOCK:
                tile_color = (120,120,120)
              elif tile_kind == MapTile.TILE_WALL:
                tile_color = (60,60,60)
              else:                                            # floor
                tile_color = (230,230,230)
            else:
              if tile_special_object == MapTile.SPECIAL_OBJECT_LAVA:
                tile_color = (200,0,0)
              elif tile_special_object == MapTile.SPECIAL_OBJECT_TELEPORT_A or tile_special_object == MapTile.SPECIAL_OBJECT_TELEPORT_B:
                tile_color = (0,0,200)
              elif tile_special_object == MapTile.SPECIAL_OBJECT_TRAMPOLINE:
                tile_color = (0,200,0)
              elif tile_kind == MapTile.TILE_FLOOR:           # arrow
                tile_color = (200,200,0)
              else:
                tile_color = (230,230,230)
            
            pygame.draw.rect(self.preview_map_image,tile_color,pygame.Rect(pos_x,pos_y,tile_size,tile_size))

        starting_positions = temp_map.get_starting_positions()

        for player_index in xrange(len(starting_positions)):
          draw_position = (int(starting_positions[player_index][0]) * tile_size + tile_half_size,int(starting_positions[player_index][1]) * tile_size + tile_half_size)
           
          pygame.draw.rect(self.preview_map_image,tile_color,pygame.Rect(pos_x,pos_y,tile_size,tile_size))
          pygame.draw.circle(self.preview_map_image,Renderer.COLOR_RGB_VALUES[player_index],draw_position,tile_half_size)

        y = tile_size * GameMap.MAP_HEIGHT + map_info_border_size
        column = 0

        self.preview_map_image.blit(self.environment_images[temp_map.get_environment_name()][0],(0,y))

        # draw starting item icons

        starting_x = Renderer.MAP_TILE_WIDTH + 5

        x = starting_x
        
        pygame.draw.rect(self.preview_map_image,(255,255,255),pygame.Rect(x,y,Renderer.MAP_TILE_WIDTH,Renderer.MAP_TILE_HEIGHT))

        starting_items = temp_map.get_starting_items()
        
        for i in xrange(len(starting_items)):
          item = starting_items[i]
          
          if item in self.icon_images:
            item_image = self.icon_images[item]
            
            self.preview_map_image.blit(item_image,(x + 1,y + 1))
            
            x += item_image.get_size()[0] + 1
            column += 1
            
            if column > 2:
              column = 0
              x = starting_x
              y += 12

  #----------------------------------------------------------------------------

  def __prerender_map(self, map_to_render):
    self.animation_events = []                  # clear previous animation

    debug_log("prerendering map...")

    # following images are only needed here, so we dont store them to self
    image_trampoline = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"other_trampoline.png"))
    image_teleport = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"other_teleport.png"))
    image_arrow_up = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"other_arrow_up.png"))
    image_arrow_right = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"other_arrow_right.png"))
    image_arrow_down = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"other_arrow_down.png"))
    image_arrow_left = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"other_arrow_left.png"))
    image_lava = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"other_lava.png"))
    image_background = pygame.image.load(os.path.join(Game.RESOURCE_PATH,"other_map_background.png"))

    self.prerendered_map_background.blit(image_background,(0,0))

    for j in xrange(GameMap.MAP_HEIGHT):
      for i in xrange(GameMap.MAP_WIDTH):
        render_position = (i * Renderer.MAP_TILE_WIDTH + Renderer.MAP_BORDER_WIDTH,j * Renderer.MAP_TILE_HEIGHT + + Renderer.MAP_BORDER_WIDTH)          
        self.prerendered_map_background.blit(self.environment_images[map_to_render.get_environment_name()][0],render_position)
       
        tile = map_to_render.get_tile_at((i,j))
          
        helper_mapping = {
            MapTile.SPECIAL_OBJECT_TELEPORT_A: image_teleport,
            MapTile.SPECIAL_OBJECT_TELEPORT_B: image_teleport,
            MapTile.SPECIAL_OBJECT_TRAMPOLINE: image_trampoline,
            MapTile.SPECIAL_OBJECT_ARROW_UP: image_arrow_up,
            MapTile.SPECIAL_OBJECT_ARROW_RIGHT: image_arrow_right,
            MapTile.SPECIAL_OBJECT_ARROW_DOWN: image_arrow_down,
            MapTile.SPECIAL_OBJECT_ARROW_LEFT: image_arrow_left,
            MapTile.SPECIAL_OBJECT_LAVA: image_lava
          }

        if tile.special_object in helper_mapping:
          self.prerendered_map_background.blit(helper_mapping[tile.special_object],render_position)
    
    game_info = map_to_render.get_game_number_info()    
      
    game_info_text = self.render_text(self.font_small,"game " + str(game_info[0]) + " of " + str(game_info[1]),(255,255,255))

    self.prerendered_map_background.blit(game_info_text,((self.prerendered_map_background.get_size()[0] - game_info_text.get_size()[0]) / 2,self.prerendered_map_background.get_size()[1] - game_info_text.get_size()[1]))

    self.prerendered_map = map_to_render

  #----------------------------------------------------------------------------

  ##< Gets an info about how given player whould be rendered in format (image to render, sprite center, relative pixel offset, draw_shadow, overlay images).

  def __get_player_render_info(self, player, game_map):
    profiler.measure_start("map rend. player")

    draw_shadow = True
    relative_offset = [0,0]
    overlay_images = []

    if player.is_dead():
      profiler.measure_stop("map rend. player")
      return (None, (0,0), (0,0), False, [])
        
    sprite_center = Renderer.PLAYER_SPRITE_CENTER
    animation_frame = (player.get_state_time() / 100) % 4
    color_index = player.get_number() if game_map.get_state() == GameMap.STATE_WAITING_TO_PLAY else player.get_team_number()

    if player.is_in_air():
      if player.get_state_time() < Player.JUMP_DURATION / 2:
        quotient = abs(player.get_state_time() / float(Player.JUMP_DURATION / 2))
      else:
        quotient = 2.0 - abs(player.get_state_time() / float(Player.JUMP_DURATION / 2))
              
      scale = (1 + 0.5 * quotient)
              
      player_image = self.player_images[color_index]["down"]
      image_to_render = pygame.transform.scale(player_image,(int(scale * player_image.get_size()[0]),int(scale * player_image.get_size()[1])))
      draw_shadow = False
              
      relative_offset[0] = -1 * (image_to_render.get_size()[0] / 2 - Renderer.PLAYER_SPRITE_CENTER[0])                   # offset caused by scale  
      relative_offset[1] = -1 * int(math.sin(quotient * math.pi / 2.0) * Renderer.MAP_TILE_HEIGHT * GameMap.MAP_HEIGHT)  # height offset

    elif player.is_teleporting():
      image_to_render = self.player_images[color_index][("up","right","down","left")[animation_frame]]

    elif player.is_boxing() or player.is_throwing():
      if not player.is_throwing() and animation_frame == 0:
        helper_string = ""
      else:
        helper_string = "box "

      helper_string += ("up","right","down","left")[player.get_direction_number()]

      image_to_render = self.player_images[color_index][helper_string]
    else:
      helper_string = ("up","right","down","left")[player.get_direction_number()]

      if player.is_walking():
        image_to_render = self.player_images[color_index]["walk " + helper_string][animation_frame]
      else:
        image_to_render = self.player_images[color_index][helper_string]

    if player.get_disease() != Player.DISEASE_NONE:
      overlay_images.append(self.other_images["disease"][animation_frame % 2]) 

    profiler.measure_stop("map rend. player") 

    return (image_to_render,sprite_center,relative_offset,draw_shadow,overlay_images)

  #----------------------------------------------------------------------------

  ##< Same as __get_player_render_info, but for bombs.

  def __get_bomb_render_info(self, bomb, game_map):
    profiler.measure_start("map rend. bomb")
    sprite_center = Renderer.BOMB_SPRITE_CENTER
    animation_frame = (bomb.time_of_existence / 100) % 4
    relative_offset = [0,0]   
    overlay_images = []      

    if bomb.has_detonator():
      overlay_images.append(self.other_images["antena"])
            
      if bomb.time_of_existence < Bomb.DETONATOR_EXPIRATION_TIME:
        animation_frame = 0                 # bomb won't pulse if within detonator expiration time

    if bomb.movement == Bomb.BOMB_FLYING:
      normalised_distance_travelled = bomb.flight_info.distance_travelled / float(bomb.flight_info.total_distance_to_travel)
            
      helper_offset = -1 * bomb.flight_info.total_distance_to_travel + bomb.flight_info.distance_travelled
            
      relative_offset = [
        int(bomb.flight_info.direction[0] * helper_offset * Renderer.MAP_TILE_WIDTH),
        int(bomb.flight_info.direction[1] * helper_offset * Renderer.MAP_TILE_HALF_HEIGHT)]

      relative_offset[1] -= int(math.sin(normalised_distance_travelled * math.pi) * bomb.flight_info.total_distance_to_travel * Renderer.MAP_TILE_HEIGHT / 2)  # height in air
          
    image_to_render = self.bomb_images[animation_frame]
          
    if bomb.has_spring:
      overlay_images.append(self.other_images["spring"])
        
    profiler.measure_stop("map rend. bomb")

    return (image_to_render,sprite_center,relative_offset,True,overlay_images)

  #----------------------------------------------------------------------------

  def render_map(self, map_to_render):
    result = pygame.Surface(self.screen_resolution)
    
    self.menu_background_image = None             # unload unneccessarry images
    self.menu_item_images = None
    self.preview_map_name = ""
    self.preview_map_image = None
    
    self.update_info_boards(map_to_render.get_players())
  
    if map_to_render != self.prerendered_map:     # first time rendering this map, prerender some stuff
      self.__prerender_map(map_to_render)

    profiler.measure_start("map rend. backg.")
    result.blit(self.prerendered_map_background,self.map_render_location)
    profiler.measure_stop("map rend. backg.")
    
    # order the players and bombs by their y position so that they are drawn correctly

    profiler.measure_start("map rend. sort")
    ordered_objects_to_render = []
    ordered_objects_to_render.extend(map_to_render.get_players())
    ordered_objects_to_render.extend(map_to_render.get_bombs())
    ordered_objects_to_render.sort(key = lambda what: 1000 if (isinstance(what,Bomb) and what.movement == Bomb.BOMB_FLYING) else what.get_position()[1])   # flying bombs are rendered above everything else
    profiler.measure_stop("map rend. sort")
    
    # render the map by lines:

    tiles = map_to_render.get_tiles()
    environment_images = self.environment_images[map_to_render.get_environment_name()]
    
    y = Renderer.MAP_BORDER_WIDTH + self.map_render_location[1]
    y_offset_block = Renderer.MAP_TILE_HEIGHT - environment_images[1].get_size()[1]
    y_offset_wall = Renderer.MAP_TILE_HEIGHT - environment_images[2].get_size()[1]
    
    line_number = 0
    object_to_render_index = 0
    
    flame_animation_frame = (pygame.time.get_ticks() / 100) % 2
    
    for line in tiles:
      x = (GameMap.MAP_WIDTH - 1) * Renderer.MAP_TILE_WIDTH + Renderer.MAP_BORDER_WIDTH + self.map_render_location[0]
      
      while True:                  # render players and bombs in the current line 
        if object_to_render_index >= len(ordered_objects_to_render):
          break
        
        object_to_render = ordered_objects_to_render[object_to_render_index]
        
        if object_to_render.get_position()[1] > line_number + 1:
          break
        
        if isinstance(object_to_render,Player):
          image_to_render, sprite_center, relative_offset, draw_shadow, overlay_images = self.__get_player_render_info(object_to_render, map_to_render)
        else:                                      # bomb
          image_to_render, sprite_center, relative_offset, draw_shadow, overlay_images = self.__get_bomb_render_info(object_to_render, map_to_render)
        
        if image_to_render == None:
          object_to_render_index += 1
          continue

        if draw_shadow:
          render_position = self.tile_position_to_pixel_position(object_to_render.get_position(),Renderer.SHADOW_SPRITE_CENTER)
          render_position = (
            (render_position[0] + Renderer.MAP_BORDER_WIDTH + relative_offset[0]) % self.prerendered_map_background.get_size()[0] + self.map_render_location[0],
            render_position[1] + Renderer.MAP_BORDER_WIDTH + self.map_render_location[1])

          result.blit(self.other_images["shadow"],render_position)
        
        render_position = self.tile_position_to_pixel_position(object_to_render.get_position(),sprite_center)
        render_position = ((render_position[0] + Renderer.MAP_BORDER_WIDTH + relative_offset[0]) % self.prerendered_map_background.get_size()[0] + self.map_render_location[0],render_position[1] + Renderer.MAP_BORDER_WIDTH + relative_offset[1] + self.map_render_location[1])
        
        result.blit(image_to_render,render_position)
        
        for additional_image in overlay_images:
          result.blit(additional_image,render_position)
      
        object_to_render_index += 1
            
      for tile in reversed(line):             # render tiles in the current line
        profiler.measure_start("map rend. tiles")
        
        if not tile.to_be_destroyed:          # don't render a tile that is being destroyed
          if tile.kind == MapTile.TILE_BLOCK:
            result.blit(environment_images[1],(x,y + y_offset_block))
          elif tile.kind == MapTile.TILE_WALL:
            result.blit(environment_images[2],(x,y + y_offset_wall))
          elif tile.item != None:
            result.blit(self.item_images[tile.item],(x,y))

        if len(tile.flames) != 0:             # if there is at least one flame, draw it
          sprite_name = tile.flames[0].direction
          result.blit(self.flame_images[flame_animation_frame][sprite_name],(x,y))

      # for debug: uncomment this to see danger values on the map
      # pygame.draw.rect(result,(int((1 - map_to_render.get_danger_value(tile.coordinates) / float(GameMap.SAFE_DANGER_VALUE)) * 255.0),0,0),pygame.Rect(x + 10,y + 10,30,30))

        x -= Renderer.MAP_TILE_WIDTH
  
        profiler.measure_stop("map rend. tiles")
  
      x = (GameMap.MAP_WIDTH - 1) * Renderer.MAP_TILE_WIDTH + Renderer.MAP_BORDER_WIDTH + self.map_render_location[0]
  
      y += Renderer.MAP_TILE_HEIGHT
      line_number += 1
      
    # update animations
    
    profiler.measure_start("map rend. anim")
    
    for animation_index in self.animations:
      self.animations[animation_index].draw(result)
    
    profiler.measure_stop("map rend. anim")
      
    # draw info boards
      
    profiler.measure_start("map rend. boards")
      
    players_by_numbers = map_to_render.get_players_by_numbers()
      
    x = self.map_render_location[0] + 12
    y = self.map_render_location[1] + self.prerendered_map_background.get_size()[1] + 20
      
    for i in players_by_numbers:
      if players_by_numbers[i] == None or self.player_info_board_images[i] == None:
        continue
        
      if players_by_numbers[i].is_dead():
        movement_offset = (0,0)
      else:
        movement_offset = (int(math.sin(pygame.time.get_ticks() / 64.0 + i) * 2),int(4 * math.sin(pygame.time.get_ticks() / 128.0 - i)))
        
      result.blit(self.player_info_board_images[i],(x + movement_offset[0],y + movement_offset[1]))
        
      x += self.gui_images["info board"].get_size()[0] - 2

    profiler.measure_stop("map rend. boards")

    profiler.measure_start("map rend. earthquake")

    if map_to_render.earthquake_is_active(): # shaking effect
      random_scale = random.uniform(0.99,1.01)
      result = pygame.transform.rotate(result,random.uniform(-4,4))
   
    profiler.measure_stop("map rend. earthquake")
   
    if map_to_render.get_state() == GameMap.STATE_WAITING_TO_PLAY:
      third = GameMap.START_GAME_AFTER / 3
      
      countdown_image_index = max(3 - map_to_render.get_map_time() / third,1)
      countdown_image = self.gui_images["countdown"][countdown_image_index]
      countdown_position = (self.screen_center[0] - countdown_image.get_size()[0] / 2,self.screen_center[1] - countdown_image.get_size()[1] / 2)
      
      result.blit(countdown_image,countdown_position)
   
    return result    

#==============================================================================
    
class AI(object):
  REPEAT_ACTIONS = (100,300)    ##< In order not to compute actions with every single call to
                                #   play(), actions will be stored in self.outputs and repeated
                                #   for next random(REPEAT_ACTIONS[0],REPEAT_ACTIONS[1]) ms - saves
                                #   CPU time and prevents jerky AI movement.

  #----------------------------------------------------------------------------
  
  def __init__(self, player, game_map):
    self.player = player
    self.game_map = game_map
    
    self.outputs = []           ##< holds currently active outputs
    self.recompute_compute_actions_on = 0
    
    self.do_nothing = False     ##< this can turn AI off for debugging purposes
    self.didnt_move_since = 0 

  #----------------------------------------------------------------------------
   
  def tile_is_escapable(self, tile_coordinates):
    if not self.game_map.tile_is_walkable(tile_coordinates) or self.game_map.tile_has_flame(tile_coordinates):
      return False
    
    tile = self.game_map.get_tile_at(tile_coordinates)
    
    if tile.special_object == MapTile.SPECIAL_OBJECT_LAVA:
      return False
    
    return True

  #----------------------------------------------------------------------------
   
  ## Returns a two-number tuple of x, y coordinates, where x and y are
  #  either -1, 0 or 1, indicating a rough general direction in which to
  #  move in order to prevent AI from walking in nonsensical direction (towards
  #  outside of the map etc.).
   
  def decide_general_direction(self):
    players = self.game_map.get_players()
    
    enemy_players = filter(lambda p: p.is_enemy(self.player) and not p.is_dead(), players)
    enemy_player = enemy_players[0] if len(enemy_players) > 0 else self.player
            
    my_tile_position = self.player.get_tile_position()
    another_player_tile_position = enemy_player.get_tile_position()

    dx = another_player_tile_position[0] - my_tile_position[0]
    dy = another_player_tile_position[1] - my_tile_position[1]
    
    dx = min(max(-1,dx),1)
    dy = min(max(-1,dy),1)
    
    return (dx,dy)
   
  #----------------------------------------------------------------------------
 
  ## Rates all 4 directions from a specified tile (up, right, down, left) with a number
  #  that says how many possible safe tiles are there accesible in that direction in
  #  case a bomb is present on the specified tile. A tuple of four integers is returned
  #  with numbers for each direction - the higher number, the better it is to run to
  #  safety in that direction. 0 means there is no escape and running in that direction
  #  means death.
    
  def rate_bomb_escape_directions(self, tile_coordinates):
                    #          up       right   down   left 
    axis_directions =          ((0,-1), (1,0),  (0,1), (-1,0))
    perpendicular_directions = ((1,0),  (0,1),  (1,0), (0,1))

    result = [0,0,0,0]
    
    for direction in (0,1,2,3):
      for i in xrange(1,self.player.get_flame_length() + 2):
        axis_tile = (tile_coordinates[0] + i * axis_directions[direction][0],tile_coordinates[1] + i * axis_directions[direction][1])
        
        if not self.tile_is_escapable(axis_tile):
          break
        
        perpendicular_tile1 = (axis_tile[0] + perpendicular_directions[direction][0],axis_tile[1] + perpendicular_directions[direction][1])
        perpendicular_tile2 = (axis_tile[0] - perpendicular_directions[direction][0],axis_tile[1] - perpendicular_directions[direction][1])

        if i > self.player.get_flame_length() and self.game_map.get_danger_value(axis_tile) >= GameMap.SAFE_DANGER_VALUE:
          result[direction] += 1
          
        if self.tile_is_escapable(perpendicular_tile1) and self.game_map.get_danger_value(perpendicular_tile1) >= GameMap.SAFE_DANGER_VALUE:
          result[direction] += 1
          
        if self.tile_is_escapable(perpendicular_tile2) and self.game_map.get_danger_value(perpendicular_tile2) >= GameMap.SAFE_DANGER_VALUE:  
          result[direction] += 1
    
    return tuple(result)

  #----------------------------------------------------------------------------
    
  ## Returns an integer score in range 0 - 100 for given file (100 = good, 0 = bad).
    
  def rate_tile(self, tile_coordinates):
    danger = self.game_map.get_danger_value(tile_coordinates)
    
    if danger == 0:
      return 0
    
    score = 0
    
    if danger < 1000:
      score = 20
    elif danger < 2500:
      score = 40
    else:
      score = 60
    
    tile_item = self.game_map.get_tile_at(tile_coordinates).item
    
    if tile_item != None:
      if tile_item != GameMap.ITEM_DISEASE:
        score += 20
      else:
        score -= 10
        
    top = (tile_coordinates[0],tile_coordinates[1] - 1)
    right = (tile_coordinates[0] + 1,tile_coordinates[1])
    down = (tile_coordinates[0],tile_coordinates[1] + 1)
    left = (tile_coordinates[0] - 1,tile_coordinates[1])
    
    if self.game_map.tile_has_lava(top) or self.game_map.tile_has_lava(right) or self.game_map.tile_has_lava(down) or self.game_map.tile_has_lava(left):
      score -= 5    # don't go near lava
    
    if self.game_map.tile_has_bomb(tile_coordinates):
      if not self.player.can_box():
        score -= 5
    
    return score

  #----------------------------------------------------------------------------
    
  def is_trapped(self):
    neighbour_tiles = self.player.get_neighbour_tile_coordinates()
  
    trapped = True
    
    for tile_coordinates in neighbour_tiles:
      if self.game_map.tile_is_walkable(tile_coordinates):
        trapped = False
        break
    
    return trapped

  #----------------------------------------------------------------------------
    
  def number_of_blocks_next_to_tile(self, tile_coordinates):
    count = 0
    
    for tile_offset in ((0,-1),(1,0),(0,1),(-1,0)):  # for each neigbour file
      helper_tile = self.game_map.get_tile_at((tile_coordinates[0] + tile_offset[0],tile_coordinates[1] + tile_offset[1]))
      
      if helper_tile != None and helper_tile.kind == MapTile.TILE_BLOCK:
        count += 1
      
    return count

  #----------------------------------------------------------------------------
    
  ## Returns a tuple in format: (nearby_enemies, nearby allies).
    
  def players_nearby(self):
    current_position = self.player.get_tile_position()
    
    allies = 0
    enemies = 0
    
    for player in self.game_map.get_players():
      if player.is_dead() or player == self.player:
        continue
      
      player_position = player.get_tile_position()
      
      if abs(current_position[0] - player_position[0]) <= 1 and abs(current_position[1] - player_position[1]) <= 1:
        if player.is_enemy(self.player):
          enemies += 1
        else:
          allies += 1
      
    return (enemies,allies)

  #----------------------------------------------------------------------------
    
  ## Decides what moves to make and returns a list of event in the same
  #  format as PlayerKeyMaps.get_current_actions().
    
  def play(self):
    if self.do_nothing or self.player.is_dead():
      return []
    
    current_time = self.game_map.get_map_time()
    
    if current_time < self.recompute_compute_actions_on or self.player.get_state() == Player.STATE_IN_AIR or self.player.get_state() == Player.STATE_TELEPORTING:
      return self.outputs          # only repeat actions
     
    # start decisions here:
    
    # moevement decisions:
    
    self.outputs = []
    
    current_tile = self.player.get_tile_position()
    trapped = self.is_trapped()
    escape_direction_ratings = self.rate_bomb_escape_directions(current_tile)
    
    # consider possible actions and find the one with biggest score:
    
    if trapped:
      # in case the player is trapped spin randomly and press box in hope to free itself
      chosen_movement_action = random.choice((PlayerKeyMaps.ACTION_UP,PlayerKeyMaps.ACTION_RIGHT,PlayerKeyMaps.ACTION_DOWN,PlayerKeyMaps.ACTION_LEFT))
    elif self.game_map.tile_has_bomb(current_tile):
      # standing on a bomb, find a way to escape
      
      # find maximum
      best_rating = escape_direction_ratings[0]
      best_action = PlayerKeyMaps.ACTION_UP
      
      if escape_direction_ratings[1] > best_rating:
        best_rating = escape_direction_ratings[1]
        best_action = PlayerKeyMaps.ACTION_RIGHT
        
      if escape_direction_ratings[2] > best_rating:
        best_rating = escape_direction_ratings[2]
        best_action = PlayerKeyMaps.ACTION_DOWN
      
      if escape_direction_ratings[3] > best_rating:
        best_rating = escape_direction_ratings[3]
        best_action = PlayerKeyMaps.ACTION_LEFT
      
      chosen_movement_action = best_action 
    else:             # not standing on a bomb
      
      # should I not move?
      
      maximum_score = self.rate_tile(current_tile)
      best_direction_actions = [None]
    
      general_direction = self.decide_general_direction()

                       # up                     # right                     # down                     # left
      tile_increment  = ((0,-1),                  (1,0),                      (0,1),                     (-1,0))
      action =          (PlayerKeyMaps.ACTION_UP, PlayerKeyMaps.ACTION_RIGHT, PlayerKeyMaps.ACTION_DOWN, PlayerKeyMaps.ACTION_LEFT)
    
      # should I move up, right, down or left?
    
      for direction in (0,1,2,3):
        score = self.rate_tile((current_tile[0] + tile_increment[direction][0],current_tile[1] + tile_increment[direction][1]))  
      
        # count in the general direction
        extra_score = 0
        
        if tile_increment[direction][0] == general_direction[0]:
          extra_score += 2
        
        if tile_increment[direction][1] == general_direction[1]:
          extra_score += 2
          
        score += extra_score
      
        if score > maximum_score:
          maximum_score = score
          best_direction_actions = [action[direction]]
        elif score == maximum_score:
          best_direction_actions.append(action[direction])
      
      chosen_movement_action = random.choice(best_direction_actions)
      
    if chosen_movement_action != None:
      if self.player.get_disease() == Player.DISEASE_REVERSE_CONTROLS:
        chosen_movement_action = PlayerKeyMaps.get_opposite_action(chosen_movement_action)
      
      self.outputs.append((self.player.get_number(),chosen_movement_action))
      
      self.didnt_move_since = self.game_map.get_map_time()

    if self.game_map.get_map_time() - self.didnt_move_since > 10000:   # didn't move for 10 seconds or more => force move
      chosen_movement_action = random.choice((PlayerKeyMaps.ACTION_UP,PlayerKeyMaps.ACTION_RIGHT,PlayerKeyMaps.ACTION_DOWN,PlayerKeyMaps.ACTION_LEFT))
      self.outputs.append((self.player.get_number(),chosen_movement_action))
      
    # bomb decisions
    
    bomb_laid = False
    
    if self.game_map.tile_has_bomb(current_tile):
      # should I throw?
      
      if self.player.can_throw() and max(escape_direction_ratings) == 0:
        self.outputs.append((self.player.get_number(),PlayerKeyMaps.ACTION_BOMB_DOUBLE))
    elif self.player.get_bombs_left() > 0 and (self.player.can_throw() or self.game_map.get_danger_value(current_tile) > 2000 and max(escape_direction_ratings) > 0): 
      # should I lay bomb?
      
      chance_to_put_bomb = 100    # one in how many
      
      players_near = self.players_nearby()
      
      if players_near[0] > 0 and players_near[1] == 0:  # enemy nearby and no ally nearby
        chance_to_put_bomb = 5
      else:
        block_tile_ratio = self.game_map.get_number_of_block_tiles() / float(GameMap.MAP_WIDTH * GameMap.MAP_HEIGHT)

        if block_tile_ratio < 0.4:   # if there is not many tiles left, put bombs more often
          chance_to_put_bomb = 80
        elif block_tile_ratio < 0.2:
          chance_to_put_bomb = 20
      
      number_of_block_neighbours = self.number_of_blocks_next_to_tile(current_tile)
     
      if number_of_block_neighbours == 1:
        chance_to_put_bomb = 3
      elif number_of_block_neighbours == 2 or number_of_block_neighbours == 3:
        chance_to_put_bomb = 2
      
      do_lay_bomb = random.randint(0,chance_to_put_bomb) == 0
      
      if do_lay_bomb:
        bomb_laid = True
        
        if random.randint(0,2) == 0 and self.should_lay_multibomb(chosen_movement_action):  # lay a single bomb or multibomb?
          self.outputs.append((self.player.get_number(),PlayerKeyMaps.ACTION_BOMB_DOUBLE))
        else:
          self.outputs.append((self.player.get_number(),PlayerKeyMaps.ACTION_BOMB))
  
    # should I box?
    
    if self.player.can_box() and not self.player.detonator_is_active():
      if trapped or self.game_map.tile_has_bomb(self.player.get_forward_tile_position()):
        self.outputs.append((self.player.get_number(),PlayerKeyMaps.ACTION_SPECIAL))
  
    if bomb_laid:   # if bomb was laid, the outputs must be recomputed fast in order to prevent laying bombs to other tiles
      self.recompute_compute_actions_on = current_time + 10
    else:
      self.recompute_compute_actions_on = current_time + random.randint(AI.REPEAT_ACTIONS[0],AI.REPEAT_ACTIONS[1])

    # should I detonate the detonator?
    
    if self.player.detonator_is_active():
      if random.randint(0,2) == 0 and self.game_map.get_danger_value(current_tile) >= GameMap.SAFE_DANGER_VALUE:
        self.outputs.append((self.player.get_number(),PlayerKeyMaps.ACTION_SPECIAL))
  
    return self.outputs

  #----------------------------------------------------------------------------

  def should_lay_multibomb(self, movement_action):
    if self.player.can_throw():    # multibomb not possible with throwing glove
      return False
    
    multibomb_count = self.player.get_multibomb_count()
    
    if multibomb_count > 1:        # multibomb possible
      current_tile = self.player.get_tile_position()

      player_direction = movement_action if movement_action != None else self.player.get_direction_number()

      # by laying multibomb one of the escape routes will be cut off, let's check
      # if there would be any escape routes left
      
      escape_direction_ratings = list(self.rate_bomb_escape_directions(current_tile))
      escape_direction_ratings[player_direction] = 0
      
      if max(escape_direction_ratings) == 0:
        return False

      direction_vector = self.player.get_direction_vector()
      
      multibomb_safe = True
      
      for i in xrange(multibomb_count):
        if not self.game_map.tile_is_walkable(current_tile) or not self.game_map.tile_is_withing_map(current_tile):
          break
        
        if self.game_map.get_danger_value(current_tile) < 3000 or self.game_map.tile_has_lava(current_tile):
          multibomb_safe = False
          break
        
        current_tile = (current_tile[0] + direction_vector[0],current_tile[1] + direction_vector[1])
        
      if multibomb_safe:
        return True
      
    return False

#==============================================================================
    
class Settings(StringSerializable):
  POSSIBLE_SCREEN_RESOLUTIONS = (
    (960,720),
    (1024,768),
    (1280,720),
    (1280,1024),
    (1366,768),
    (1680,1050),
    (1920,1080)
    )
  
  SOUND_VOLUME_THRESHOLD = 0.01
  CONTROL_MAPPING_DELIMITER = "CONTROL MAPPING"
  
  #----------------------------------------------------------------------------

  def __init__(self, player_key_maps):
    self.player_key_maps = player_key_maps
    self.reset()

  #----------------------------------------------------------------------------
         
  def reset(self):
    self.sound_volume = 0.7
    self.music_volume = 0.2
    self.screen_resolution = Settings.POSSIBLE_SCREEN_RESOLUTIONS[0]
    self.fullscreen = False
    self.control_by_mouse = False
    self.player_key_maps.reset()

  #----------------------------------------------------------------------------

  def save_to_string(self):
    result = ""
    
    result += "sound volume: " + str(self.sound_volume) + "\n"
    result += "music volume: " + str(self.music_volume) + "\n"
    result += "screen resolution: " + str(self.screen_resolution[0]) + "x" + str(self.screen_resolution[1]) + "\n"
    result += "fullscreen: " + str(self.fullscreen) + "\n"
    result += "control by mouse: " + str(self.control_by_mouse) + "\n"
    result += Settings.CONTROL_MAPPING_DELIMITER + "\n"
    
    result += self.player_key_maps.save_to_string() + "\n"

    result += Settings.CONTROL_MAPPING_DELIMITER + "\n"
    
    return result

  #----------------------------------------------------------------------------
    
  def load_from_string(self, input_string):
    self.reset()
    
    helper_position = input_string.find(Settings.CONTROL_MAPPING_DELIMITER)
    
    if helper_position >= 0:
      helper_position1 = helper_position + len(Settings.CONTROL_MAPPING_DELIMITER)
      helper_position2 = input_string.find(Settings.CONTROL_MAPPING_DELIMITER,helper_position1)

      debug_log("loading control mapping")

      settings_string = input_string[helper_position1:helper_position2].lstrip().rstrip()
      self.player_key_maps.load_from_string(settings_string)

      input_string = input_string[:helper_position] + input_string[helper_position2 + len(Settings.CONTROL_MAPPING_DELIMITER):]
    
    lines = input_string.split("\n")
    
    for line in lines:
      helper_position = line.find(":")
      
      if helper_position < 0:
        continue
      
      key_string = line[:helper_position]
      value_string = line[helper_position + 1:].lstrip().rstrip()
      
      if key_string == "sound volume":
        self.sound_volume = float(value_string)
      elif key_string == "music volume":
        self.music_volume = float(value_string)
      elif key_string == "screen resolution":
        helper_tuple = value_string.split("x")
        self.screen_resolution = (int(helper_tuple[0]),int(helper_tuple[1]))
      elif key_string == "fullscreen":
        self.fullscreen = True if value_string == "True" else False     
      elif key_string == "control by mouse":
        self.control_by_mouse = True if value_string == "True" else False

  #----------------------------------------------------------------------------
    
  def sound_is_on(self):
    return self.sound_volume > Settings.SOUND_VOLUME_THRESHOLD

  #----------------------------------------------------------------------------
  
  def music_is_on(self):
    return self.music_volume > Settings.SOUND_VOLUME_THRESHOLD

  #----------------------------------------------------------------------------
   
  def current_resolution_index(self):
    return next((i for i in xrange(len(Settings.POSSIBLE_SCREEN_RESOLUTIONS)) if self.screen_resolution == Settings.POSSIBLE_SCREEN_RESOLUTIONS[i]),0)

#==============================================================================
    
class Game(object):    
  # colors used for players and teams
  COLOR_WHITE = 0
  COLOR_BLACK = 1
  COLOR_RED = 2
  COLOR_BLUE = 3
  COLOR_GREEN = 4
  COLOR_CYAN = 5
  COLOR_YELLOW = 6
  COLOR_ORANGE = 7
  COLOR_BROWN = 8
  COLOR_PURPLE = 9

  COLOR_NAMES = [
    "white",
    "black",
    "red",
    "blue",
    "green",
    "cyan",
    "yellow",
    "orange",
    "brown",
    "purple"
    ]
    
  STATE_PLAYING = 0
  STATE_EXIT = 1
  STATE_MENU_MAIN = 2
  STATE_MENU_SETTINGS = 3
  STATE_MENU_ABOUT = 4
  STATE_MENU_PLAY_SETUP = 5
  STATE_MENU_MAP_SELECT = 6
  STATE_MENU_CONTROL_SETTINGS = 7
  STATE_MENU_PLAY = 8
  STATE_MENU_RESULTS = 9
  STATE_GAME_STARTED = 10
  
  CHEAT_PARTY = 0
  CHEAT_ALL_ITEMS = 1
  CHEAT_PLAYER_IMMORTAL = 2
  
  VERSION_STR = "0.95"
  
  NUMBER_OF_CONTROLLED_PLAYERS = 4    ##< maximum number of non-AI players on one PC
  
  RESOURCE_PATH = "resources"
  MAP_PATH = "maps"
  SETTINGS_FILE_PATH = "settings.txt"

  #----------------------------------------------------------------------------
  
  def __init__(self):
    pygame.mixer.pre_init(22050,-16,2,512)   # set smaller audio buffer size to prevent audio lag
    pygame.init()
    pygame.font.init()
    pygame.mixer.init()
    
    self.frame_number = 0
    
    self.player_key_maps = PlayerKeyMaps()
    
    self.settings = Settings(self.player_key_maps)
    
    self.game_number = 0
    
    if os.path.isfile(Game.SETTINGS_FILE_PATH):
      debug_log("loading settings from file " + Game.SETTINGS_FILE_PATH)
      
      self.settings.load_from_file(Game.SETTINGS_FILE_PATH)
 
    self.settings.save_to_file(Game.SETTINGS_FILE_PATH)  # save the reformatted settings file (or create a new one)
    
    pygame.display.set_caption("Bombman")
    
    self.renderer = Renderer()
    self.apply_screen_settings()
    
    self.sound_player = SoundPlayer()
    self.sound_player.change_music()
    self.apply_sound_settings()
    
    self.apply_other_settings()
             
    self.map_name = ""
    self.random_map_selection = False
    self.game_map = None
    
    self.play_setup = PlaySetup()
    
    self.menu_main = MainMenu(self.sound_player)
    self.menu_settings = SettingsMenu(self.sound_player,self.settings,self)
    self.menu_about = AboutMenu(self.sound_player)
    self.menu_play_setup = PlaySetupMenu(self.sound_player,self.play_setup)
    self.menu_map_select = MapSelectMenu(self.sound_player)
    self.menu_play = PlayMenu(self.sound_player)
    self.menu_controls = ControlsMenu(self.sound_player,self.player_key_maps,self)
    self.menu_results = ResultMenu(self.sound_player)
    
    self.ais = []
    
    self.state = Game.STATE_MENU_MAIN

    self.immortal_players_numbers = []
    self.active_cheats = set()

  #----------------------------------------------------------------------------

  def deactivate_all_cheats(self):
    self.active_cheats = set()

    debug_log("all cheats deactivated")

  #----------------------------------------------------------------------------
      
  def activate_cheat(self, what_cheat):
    self.active_cheats.add(what_cheat)
    
    debug_log("cheat activated")

  #----------------------------------------------------------------------------
    
  def deactivate_cheat(self, what_cheat):
    if what_cheat in self.active_cheats:
      self.active_cheats.remove(what_cheat)

  #----------------------------------------------------------------------------

  def cheat_is_active(self, what_cheat):
    return what_cheat in self.active_cheats

  #----------------------------------------------------------------------------

  def get_player_key_maps(self):
    return self.player_key_maps

  #----------------------------------------------------------------------------

  def get_settings(self):
    return self.settings

  #----------------------------------------------------------------------------

  def apply_screen_settings(self):
    display_flags = 0
    
    if self.settings.fullscreen:
      display_flags += pygame.FULLSCREEN
 
    self.screen = pygame.display.set_mode(self.settings.screen_resolution,display_flags)
    
    screen_center = (Renderer.get_screen_size()[0] / 2,Renderer.get_screen_size()[1] / 2)
    pygame.mouse.set_pos(screen_center)
    
    self.renderer.update_screen_info()

  #----------------------------------------------------------------------------
  
  def apply_sound_settings(self):
    self.sound_player.set_music_volume(self.settings.music_volume)
    self.sound_player.set_sound_volume(self.settings.sound_volume)

  #----------------------------------------------------------------------------
  
  def apply_other_settings(self):
    self.player_key_maps.allow_control_by_mouse(self.settings.control_by_mouse)

  #----------------------------------------------------------------------------
  
  def save_settings(self):
    self.settings.save_to_file(Game.SETTINGS_FILE_PATH)

  #----------------------------------------------------------------------------

  def __check_cheat(self, cheat_string, cheat = None):
    if self.player_key_maps.string_was_typed(cheat_string):
      if cheat != None:
        self.activate_cheat(cheat)
      else:
        self.deactivate_all_cheats()

      self.player_key_maps.clear_typing_buffer()

  #----------------------------------------------------------------------------

  ## Manages the menu actions and sets self.active_menu.

  def manage_menus(self):
    new_state = self.state
    prevent_input_processing = False
    
    # cheack if any cheat was typed:
    self.__check_cheat("party",game.CHEAT_PARTY)
    self.__check_cheat("herecomedatboi",game.CHEAT_ALL_ITEMS)
    self.__check_cheat("leeeroy",game.CHEAT_PLAYER_IMMORTAL)
    self.__check_cheat("revert")

    self.player_key_maps.get_current_actions()       # this has to be called in order for player_key_maps to update mouse controls properly
      
    # ================ MAIN MENU =================
    if self.state == Game.STATE_MENU_MAIN: 
      self.active_menu = self.menu_main
      
      if self.active_menu.get_state() == Menu.MENU_STATE_CONFIRM:
        new_state = [
          Game.STATE_MENU_PLAY_SETUP,
          Game.STATE_MENU_SETTINGS,
          Game.STATE_MENU_ABOUT,
          Game.STATE_EXIT
          ] [self.active_menu.get_selected_item()[0]]

    # ================ PLAY MENU =================
    elif self.state == Game.STATE_MENU_PLAY:
      self.active_menu = self.menu_play

      if self.active_menu.get_state() == Menu.MENU_STATE_CANCEL:
        new_state = Game.STATE_PLAYING

      elif self.active_menu.get_state() == Menu.MENU_STATE_CONFIRM:
        if self.active_menu.get_selected_item() == (0,0):
          new_state = Game.STATE_PLAYING
          
          for player in self.game_map.get_players():
            player.wait_for_bomb_action_release()
          
        elif self.active_menu.get_selected_item() == (1,0):
          new_state = Game.STATE_MENU_MAIN
          self.sound_player.change_music()
          self.deactivate_all_cheats()
    
    # ============== SETTINGS MENU ===============
    elif self.state == Game.STATE_MENU_SETTINGS: 
      self.active_menu = self.menu_settings
      
      if self.active_menu.get_state() == Menu.MENU_STATE_CANCEL:
        new_state = Game.STATE_MENU_MAIN
      elif self.active_menu.get_state() == Menu.MENU_STATE_CONFIRM:
        if self.active_menu.get_selected_item() == (5,0):
          new_state = Game.STATE_MENU_CONTROL_SETTINGS
        elif self.active_menu.get_selected_item() == (7,0):
          new_state = Game.STATE_MENU_MAIN

    # ========== CONTROL SETTINGS MENU ===========
    elif self.state == Game.STATE_MENU_CONTROL_SETTINGS:
      self.active_menu = self.menu_controls
      self.active_menu.update(self.player_key_maps)    # needs to be called to scan for pressed keys
      
      if self.active_menu.get_state() == Menu.MENU_STATE_CANCEL:
        new_state = Game.STATE_MENU_SETTINGS
      elif self.active_menu.get_state() == Menu.MENU_STATE_CONFIRM:
        if self.active_menu.get_selected_item() == (0,0):
          new_state = Game.STATE_MENU_SETTINGS
        
    # ================ ABOUT MENU =================
    elif self.state == Game.STATE_MENU_ABOUT: 
      self.active_menu = self.menu_about
      
      if self.active_menu.get_state() in (Menu.MENU_STATE_CONFIRM,Menu.MENU_STATE_CANCEL):
        new_state = Game.STATE_MENU_MAIN
    
    # ============== PLAY SETUP MENU ==============
    elif self.state == Game.STATE_MENU_PLAY_SETUP: 
      self.active_menu = self.menu_play_setup
      
      if self.active_menu.get_state() == Menu.MENU_STATE_CANCEL:
        new_state = Game.STATE_MENU_MAIN
      elif self.active_menu.get_state() == Menu.MENU_STATE_CONFIRM:
        if self.active_menu.get_selected_item() == (0,1):
          new_state = Game.STATE_MENU_MAP_SELECT
        elif self.active_menu.get_selected_item() == (0,0):
          new_state = Game.STATE_MENU_MAIN
    
    # ============== MAP SELECT MENU ==============
    elif self.state == Game.STATE_MENU_MAP_SELECT:
      self.active_menu = self.menu_map_select
      
      if self.active_menu.get_state() == Menu.MENU_STATE_CANCEL:
        new_state = Game.STATE_MENU_PLAY_SETUP
      elif self.active_menu.get_state() == Menu.MENU_STATE_CONFIRM:
        self.map_name = self.active_menu.get_selected_map_name()
        self.random_map_selection = self.active_menu.random_was_selected()
        self.game_number = 1     # first game
        new_state = Game.STATE_GAME_STARTED
        
        self.deactivate_cheat(Game.CHEAT_PARTY)
    
    # ================ RESULT MENU ================
    elif self.state == Game.STATE_MENU_RESULTS:
      self.active_menu = self.menu_results
    
      if self.active_menu.get_state() in (Menu.MENU_STATE_CONFIRM,Menu.MENU_STATE_CANCEL):
        new_state = Game.STATE_MENU_MAIN
      
    if new_state != self.state:  # going to new state
      self.state = new_state
      self.active_menu.leaving()
    
    self.active_menu.process_inputs(self.player_key_maps.get_current_actions())

  #----------------------------------------------------------------------------

  def acknowledge_wins(self, winner_team_number, players):
    for player in players:
      if player.get_team_number() == winner_team_number:
        player.set_wins(player.get_wins() + 1)    

  #----------------------------------------------------------------------------

  def run(self):
    time_before = pygame.time.get_ticks()

    show_fps_in = 0
    pygame_clock = pygame.time.Clock()

    while True:                                  # main loop
      profiler.measure_start("main loop")
      
      dt = min(pygame.time.get_ticks() - time_before,100)
      time_before = pygame.time.get_ticks()

      pygame_events = []

      for event in pygame.event.get():
        if event.type == pygame.QUIT:
          self.state = Game.STATE_EXIT
        
        pygame_events.append(event)

      self.player_key_maps.process_pygame_events(pygame_events,self.frame_number)

      if self.state == Game.STATE_PLAYING:
        self.renderer.process_animation_events(self.game_map.get_and_clear_animation_events()) # play animations
        self.sound_player.process_events(self.game_map.get_and_clear_sound_events())           # play sounds
        
        profiler.measure_start("map rend.")
        self.screen.blit(self.renderer.render_map(self.game_map),(0,0)) 
        profiler.measure_stop("map rend.")
        
        profiler.measure_start("sim.")
        self.simulation_step(dt)
        profiler.measure_stop("sim.")
        
        if self.game_map.get_state() == GameMap.STATE_GAME_OVER:
          self.game_number += 1
          
          if self.game_number > self.play_setup.get_number_of_games():
            previous_winner = self.game_map.get_winner_team()
            self.acknowledge_wins(previous_winner,self.game_map.get_players())
            self.menu_results.set_results(self.game_map.get_players())
            self.game_map = None
            self.state = Game.STATE_MENU_RESULTS   # show final results
            self.deactivate_all_cheats()
          else:
            self.state = Game.STATE_GAME_STARTED   # new game
      elif self.state == Game.STATE_GAME_STARTED:
        debug_log("starting game " + str(self.game_number))
    
        previous_winner = -1
    
        if self.game_number != 1:
          previous_winner = self.game_map.get_winner_team()
        
        kill_counts = [0 for i in xrange(10)]
        win_counts = [0 for i in xrange(10)]
        
        if self.game_map != None:
          for player in self.game_map.get_players():
            kill_counts[player.get_number()] = player.get_kills()
            win_counts[player.get_number()] = player.get_wins()
        
        map_name_to_load = self.map_name if not self.random_map_selection else self.menu_map_select.get_random_map_name()
        
        with open(os.path.join(Game.MAP_PATH,map_name_to_load)) as map_file:
          map_data = map_file.read()
          self.game_map = GameMap(map_data,self.play_setup,self.game_number,self.play_setup.get_number_of_games(),self.cheat_is_active(Game.CHEAT_ALL_ITEMS))
          
        player_slots = self.play_setup.get_slots()
        
        if self.cheat_is_active(Game.CHEAT_PLAYER_IMMORTAL):
          self.immortal_players_numbers = []
          
          for i in xrange(len(player_slots)):
            if player_slots[i] != None and player_slots[i][0] >= 0:   # cheat: if not AI
              self.immortal_players_numbers.append(i)                 # make the player immortal
        
        self.ais = []
        
        for i in xrange(len(player_slots)):
          if player_slots[i] != None and player_slots[i][0] < 0:  # indicates AI
            self.ais.append(AI(self.game_map.get_players_by_numbers()[i],self.game_map))
      
        for player in self.game_map.get_players():
          player.set_kills(kill_counts[player.get_number()])
          player.set_wins(win_counts[player.get_number()])
        
        self.acknowledge_wins(previous_winner,self.game_map.get_players())    # add win counts
        
        self.sound_player.change_music()
        self.state = Game.STATE_PLAYING
      elif self.state == Game.STATE_EXIT:
        break
      else:   # in menu
        self.manage_menus()
        
        profiler.measure_start("menu rend.")
        self.screen.blit(self.renderer.render_menu(self.active_menu,self),(0,0))  
        profiler.measure_stop("menu rend.")

      pygame.display.flip()
      pygame_clock.tick()

      if show_fps_in <= 0:
        if DEBUG_FPS:
          debug_log("fps: " + str(pygame_clock.get_fps()))

        show_fps_in = 255
      else:
        show_fps_in -= 1
        
      self.frame_number += 1
      
      profiler.measure_stop("main loop")
      
      if DEBUG_PROFILING:
        debug_log(profiler.get_profile_string())
        profiler.end_of_frame()

  #----------------------------------------------------------------------------

  ## Filters a list of performed actions so that there are no actions of
  #  human players that are not participating in the game.

  def filter_out_disallowed_actions(self, actions):
    player_slots = self.play_setup.get_slots()
    result = filter(lambda a: (player_slots[a[0]] != None and player_slots[a[0]] >=0) or (a[1] == PlayerKeyMaps.ACTION_MENU), actions)    
    return result

  #----------------------------------------------------------------------------

  def simulation_step(self, dt):
    actions_being_performed = self.filter_out_disallowed_actions(self.player_key_maps.get_current_actions())
    
    for action in actions_being_performed:
      if action[0] == -1:                                # menu key pressed
        self.state = Game.STATE_MENU_PLAY
        return
    
    profiler.measure_start("sim. AIs")
    
    for i in xrange(len(self.ais)):
      actions_being_performed = actions_being_performed + self.ais[i].play()
      
    profiler.measure_stop("sim. AIs")
    
    players = self.game_map.get_players()

    profiler.measure_start("sim. inputs")
    
    for player in players:
      player.react_to_inputs(actions_being_performed,dt,self.game_map)
      
    profiler.measure_stop("sim. inputs")
      
    profiler.measure_start("sim. map update")
    
    self.game_map.update(dt,self.immortal_players_numbers)
    
    profiler.measure_stop("sim. map update")

  #----------------------------------------------------------------------------

  ## Sets up a test game for debugging, so that the menus can be avoided.
 
  def setup_test_game(self, setup_number = 0):
    if setup_number == 0:
      self.map_name = "classic"
      self.random_map_selection = False
      self.game_number = 1
      self.state = Game.STATE_GAME_STARTED
    elif setup_number == 1:
      self.play_setup.player_slots = [(-1,i) for i in xrange(10)]
      self.random_map_selection = True
      self.game_number = 1
      self.state = Game.STATE_GAME_STARTED      
    else:
      self.play_setup.player_slots = [((i,i) if i < 4 else None) for i in xrange(10)]
      self.map_name = "classic"
      self.game_number = 1
      self.state = Game.STATE_GAME_STARTED      

#==============================================================================
    
if __name__ == "__main__":
  profiler = Profiler()   # profiler object is global, for simple access
  game = Game()

  if len(sys.argv) > 1: 
    if "--test" in sys.argv:       # allows to quickly init a game
      game.setup_test_game(0)
    elif "--test2" in sys.argv:
      game.setup_test_game(1)
    elif "--test3" in sys.argv:
      game.setup_test_game(2)

  game.run()
