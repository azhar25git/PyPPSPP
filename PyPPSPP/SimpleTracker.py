import logging
import socket
import random

import ALTOInterface

class SimpleTracker(object):
    """This class abstracts a simple tracket. It can later be replaced with PPSP-TP"""

    def __init__(self):
        self._tracekr_protocol = None
        self._myip = self._get_my_ip()
        self._hive = None
        self._use_alto = False
        self._alto = None

    def set_use_alto(self):
        self._use_alto = True
        self._alto = ALTOInterface.ALTOInterface("http://10.0.102.4:5000")
        self._alto.get_costmap()
        self._alto.get_networkmap()

    def set_hive(self, hive):
        """Link tracker to the hive"""
        self._hive = hive

    def set_tracker_protocol(self, proto):
        self._tracekr_protocol = proto

    def connection_lost(self):
        """Connection to the tracker was lost..."""
        # We can continue operating even if connection to the tracker is lost
        return None

    def _get_my_ip(self):
        """Get My IP address. This is an awful hack"""
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('1.1.1.1', 0))
        return s.getsockname()[0]

    def data_received(self, data):
        """Called with deserialized message from the tracker server"""

        swarm_id = None
        if 'swarm_id' not in data:
            logging.warn("Received data from tracker without swarm identifier. Data: {}"
                         .format(data))
            return

        swarm_id = data['swarm_id']
        swarm = self._hive.get_swarm(swarm_id)

        if swarm is None:
            logging.warn("Received data from tracker for unknown swarm! Swarm ID:{}"
                         .format(swarm_id))
            return

        if data['type'] == 'other_peers':
            # We got information about other peers in the system
            if not any(data['details']):
                return

            # Always save information about other peers
            swarm.add_other_peers([tuple(x) for x in data['details']])

            # If we are live source - let others connect to us
            if swarm.live and swarm.live_src:
                return

            if self._use_alto:
                self.handle_other_peers_alto(swarm, data)
                return
            else:
                self.handle_other_peers(swarm, data)
                return
        elif data['type'] == 'new_node':
            endpoint = data['endpoint']
            logging.info('Received new_node from tracker. Node: {}:{}'
                         .format(endpoint[0], endpoint[1]))

            # Add to known peers list
            swarm.add_other_peers([tuple(endpoint)])

            # If we are live source - let others connect to us
            if swarm.live and swarm.live_src:
                return

            if swarm.any_free_peer_slots():
                self.add_tcp_member(swarm, endpoint[0], endpoint[1])
            else:
                logging.info('Swarm {} has no free slots. Ignoring'.format(swarm.swarm_id))
        elif data['type'] == 'remove_node':
            swarm.remove_other_peers([tuple(data['endpoint'])])
        else:
            logging.warn('Unknown message received from the tracker: {}'
                         .format(data['type']))

    def add_tcp_member(self, swarm, ip_address, port):
        """Handle making connection to the peer and adding it to swarm"""
        # Check if we have connection already
        proto = self._hive.get_proto_by_address(ip_address, port)
        if proto is not None:
            # Connection to the given peer is already there - start handshake
            member = swarm.AddMember(ip_address, port, proto)
            if isinstance(member, str):
                # Some error
                pass
            else:
                member.SendHandshake()
        else:
            # Initiate a new coonection to the given peer
            self._hive.make_connection(ip_address, port, swarm.swarm_id)

    def handle_other_peers(self, swarm, data):
        """Handle other_peers message when not using ALTO"""
        
        # Shuffle the received members list
        mem_copy = data['details']
        random.shuffle(mem_copy)

        for member in mem_copy:
            if swarm._args.tcp:
                self.add_tcp_member(swarm, member[0], member[1])
            else:
                # This is UDP
                m = swarm.AddMember(member[0], member[1])
                if isinstance(m, str):
                    pass
                else:
                    m.SendHandshake()

    def handle_other_peers_alto(self, swarm, data):
        """Handle other_peers message when using ALTO"""
        # Prepare data
        net_costs = {}
        my_ip = self._GetMyIP()

        # Sort into price buckets
        for member in data['details']:
            mem_cost = int(self._alto.get_cost_by_ip(my_ip, member[0]))
            if mem_cost not in net_costs:
                net_costs[mem_cost] = []
            net_costs[mem_cost].append(member)

        # Log our costs
        logging.info("ALTO Sorted: {}".format(net_costs))

        # Start adding
        costs = list(net_costs.keys())
        costs.sort()

        # Add members
        for cost in costs:
            for member in net_costs[cost]:
                m = self._swarm.AddMember(member[0], member[1])
                if isinstance(m, str):
                    pass
                else:
                    m.SendHandshake()

    def register_in_tracker(self, swarm_id: str, port: int):
        """Register with the tracker"""

        data = {}
        data['type'] = 'register'
        data['swarm_id'] = swarm_id
        data['endpoint'] = (self._myip, port)

        self._tracekr_protocol.SendData(data)

    def unregister_from_tracker(self, swarm_id: str):
        """Inform tracker that we are leaving"""
        
        data = {}
        data['type'] = 'unregister'
        data['swarm_id'] = swarm_id
        data['endpoint'] = (self._myip, 6778)

        self._tracekr_protocol.SendData(data)

    def get_peers(self, swarm_id: str):
        """Request list of peers from the tracker"""
        
        data = {}
        data['type'] = 'get_peers'
        data['swarm_id'] = swarm_id

        self._tracekr_protocol.SendData(data)