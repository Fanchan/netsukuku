##
# This file is part of Netsukuku
# (c) Copyright 2007 Alberto Santini <alberto@unix-monk.com>
#
# This source code is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as published 
# by the Free Software Foundation; either version 2 of the License,
# or (at your option) any later version.
#
# This source code is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# Please refer to the GNU Public License for more details.
#
# You should have received a copy of the GNU Public License along with
# this source code; if not, write to:
# Free Software Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
##

from xtime import swait
from time import *
from micro import micro
from route import Rtt
from operator import itemgetter

class Neigh:
  """ this class simply represent a neighbour """
  def __init__(self, nip, idn, rtt):
    # nip: the neighbour's IP;
    # idn: the neighbour's ID;
    # rtt: the neighbour's Round Trip Time;

    self.ip = ip
    self.id = idn
    self.rem = Rtt(rtt)

class Neighbour:
  """ this class manages all neighbours """
  def __init__(self, multipath = 0, max_neigh = 16):
    # multipath: does the current kernel we're running on support multipath routing?;
    # max_neigh: maximum number of neighbours we can have;

    self.multipath = multipath
    self.max_neigh = max_neigh
    # variation on neighbours' rtt greater than this will be notified
    self.rtt_variation = 0.1
    # our ip_table
    self.ip_table = {}
    # our IP => ID translation table
    self.translation_table = {}
    # the events we raise
    self.events = Event(['NEW_NEIGH', 'DEL_NEIGH', 'REM_NEIGH'])

  def neigh_list(self):
    # return the list of neighbours
    nlist = []
    for key, val in ip_table:
      nlist.append(Neigh(key, translation_table[key], val[1]))
    return nlist

  def ip_to_id(self, ipn):
    # if ipn is in the translation table, return the associated id;
    # if it isn't, insert it into the translation table assigning a new id,
    # if the table isn't full;

    if(self.translation_table.has_key(ipn)):
      return self.translation_table[ipn]
    new_id = self.find_hole_in_tt
    if new_id:
      self.translation_table[ipn] = new_id
      return new_id
    else:
      return False

  def truncate(self, ip_table):
    # ip_table: an {IP => [dev, rtt]};
    # we want the best (with the lowest rtt) max_neigh nodes only to remain in the table

    # auxiliary function, to take rtt from {IP => [dev,rtt]}
    def interesting(x):
      return x[1][1]

    # remember who we are truncating
    trucated = []

    # the new table, without truncated rows
    ip_table_trunc = {}

    # a counter
    counter = 0

    # we're cycling through ip_table, ordered by rtt
    for key, val in sorted(ip_table.items(), reverse = False, key = interesting):
      # if we haven't still reached max_neigh entries in the new ip_table
      if(counter < self.max_neigh):
        # add the current row into ip_table """
        ip_table_trunc[key] = val
      else:
        # otherwise just drop it
        # but, if old ip_table contained this row, we should notify our listeners about this:
        if(self.ip_table.has_key(key)):
          # remember we are truncating this row
          trucated.append(key)
          # remember its id
          old_id = self.translation_table(key)
          # delete the entry from the translation table
          self.translation_table.pop(key)
          # send a message notifying we deleted the entry
          self.events.send('DEL_NEIGH', (Neigh(key, old_id, None)))
    # return the new ip_table and the list of truncated entries
    return (ip_table_trunc, truncated)

  def find_hole_in_tt(self):
    # find the first available index in translation_table
    for i in xrange(self.max_neigh):
      if((i in self.translation_table) == False):
        return i
    return False

  def store(self, ip_table):
    # ip_table: the new ip_table;
    # substitute the old ip_table with the new and notify about the changes

    # the rows deleted during truncation
    died_ip_list = []

    (ip_table, died_ip_list) = self.truncate(ip_table)

    # first of all we cycle through the old ip_table
    # looking for nodes that aren't in the new one
    for key in self.ip_table:
      # if we find a row that isn't in the new ip_table and whose
      # deletion hasn't already been notified (raising an event)
      # during truncation
      if((not (ip_table.has_key(key))) and (not (key in died_ip_list))):
        # remember its id
        old_id = self.translation_table(key)
        # delete the entry from the translation table
        self.translation_table.pop(key)
        # send a message notifying we deleted the entry
        self.events.send('DEL_NEIGH', (Neigh(key, old_id, None)))

    # now we cycle through the new ip_table
    # looking for nodes who weren't in the old one
    # or whose rtt has sensibly changed
    for key in ip_table:
      # if a node has been added
      if(not (self.ip_table.has_key(key))):
        # generate an id and add the entry in translation_table
        ip_to_id(key)
        # send a message notifying we added a node
        self.events.send('NEW_NEIGH', (Neigh(key, self.translation_table(key), self.ip_table[key][1])))
      else:
        # otherwise (if the node already was in old ip_table) check if
        # its rtt has changed more than rtt_variation
        if(abs(ip_table[key][1] - self.ip_table[key][1]) / self.ip_table[key][1] > self.rtt_mav_var):
          # send a message notifying the node's rtt changed
          self.events.send('REM_NEIGH', (Neigh(key, self.translation_table(key), ip_table[key][1]), self.ip_table[key][1]))

    # finally, update the ip_table
    self.ip_table = ip_table

class Radar:
  def __init__(self, multipath = 0, bquet_num = 16, max_neigh = 16, max_wait_time = 10):
    # multipath: does the current kernel we're running on support multipath routing?;
    #    bquet_num: how many packets does each bouquet contain?;
    #    max_neigh: maximum number of neighbours we can have;
    #    max_wait_time: the maximum time we can wait for a reply, in seconds;

    # when we sent the broadcast packets
    self.bcast_send_time = 0
    # when the replies arrived
    self.bcast_arrival_time = {}
    self.bquet_dimension = bquet_num
    self.multipath = multipath
    self.max_wait_time = max_wait_time
    # an instance of the Broadcast class to manage broadcast sending
    self.broadcast = Broadcast(time_register)
    # our neighbours
    self.neigh = Neighbour(multipath, max_neigh)

  def radar(self):
    # Send broadcast packets and store the results in neigh

    # we're sending the broadcast packets NOW
    self.bcast_send_time = time.time()

    # send all packets in the bouquet
    def br():
      broadcast.reply()
    for i in xrange(bquet_num):
      micro(br)

    # then wait
    swait(self.max_wait_time * 1000)

    # update the neighbours' ip_table
    self.neigh.store(self.get_all_avg_rtt())

  def reply(self):
    ### just do nothing
    pass

  def time_register(self, ip, net_device):
    # save each node's rtt

    # this is the rtt
    time_elapsed = int(time.time() - bcast_send_time * 1000 / 2)
    # let's store it in the bcast_arrival_time table
    if(self.bcast_arrival_time.has_key(ip)):
      if(self.bcast_arrival_time(ip).has_key(net_device)):
        self.bcast_arrival_time[ip].append(time_elapsed)
      else:
        self.bcast_arrival_time[ip][net_device] = [time_elapsed]
    else:
      self.bcast_arrival_time[ip] = {}
      self.bcast_arrival_time[ip][net_device] = [time_elapsed]

  def get_avg_rtt(self, ip):
    # ip: an ip;
    # calculate the average rtt of ip

    if(self.multipath == 0):
      # if we can't use multipath routing use the value from the best nic
      best_dev = None
      best_rtt = float("infinity")
      # for each nic
      for dev in self.bcast_arrival_time[ip]:
        # calculate the average rtt
        avg = sum(self.bcast_arrival_time[node][dev]) / len(self.bcast_arrival_time[node][dev])
        # and check if it's the current best
        if(avg <= best_time):
          best_dev = dev
          best_rtt = avg
      # finally return which nic had the best average rtt and what was it
      return [best_dev, best_rtt]
    else:
      # otherwise use the value from all the nics
      counter = 0
      sum = 0
      # for each nic
      for dev in self.bcast_arrival_time[ip]:
        # for each time measurement
        for time in self.bcast_arrival_time[ip][dev]:
          # just add it to the total sum
          sum += time
          # and update the counter
          counter += 1
      # finally return the average rtt
      return (sum / counter)

  def get_all_avg_rtt(self):
    # calculate the average rtt of all the ips

    all_avg = {}
    # for each ip
    for ip in self.bcast_arrival_time:
      # if we can't use multipath routing
      if(self.multipath == 0):
        # simply store get_avg_rtt's value
        all_avg[ip] = get_avg_rtt(ip)
      else:
        # otherwise, set None as the device
        all_avg[ip] = [None, get_avg_rtt(ip)]
    return all_avg