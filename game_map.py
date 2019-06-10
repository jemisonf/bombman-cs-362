from bombman import *

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
    
    # function call to translate map data on tiles into MapTile objects
    
    tile_translator(string_split[3], block_tiles)

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
  def tile_translator(self, tileData, block_tiles):


    teleport_a_tile = None       # helper variables used to pair teleports
    teleport_b_tile = None
    self.number_of_blocks = 0    ##< says how many block tiles there are currently on the map

    column = 0
    line = -1
    block_tiles = []
    for i in xrange(len(tileData):
      tile_character = tileData[i]

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