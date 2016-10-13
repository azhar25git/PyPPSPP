import time
import asyncio
import collections
import struct
import logging

from Messages import *
from AbstractSendRequestedChunks import AbstractSendRequestedChunks

class LEDBATSendRequestedChunks(AbstractSendRequestedChunks):
    """Sending of requested chunks using LEDBAT"""
    WINDOWLEN = 5

    def __init__(self, swarm, member):
        self._ret_control = collections.deque(
           LEDBATSendRequestedChunks.WINDOWLEN * [None],
           LEDBATSendRequestedChunks.WINDOWLEN)
        return super().__init__(swarm, member)

    def _build_and_send(self, chunk_id):
        """Build DATA message with indicated chunk"""
        data = self._swarm.GetChunkData(chunk_id)
        
        md = MsgData.MsgData(self._member.chunk_size, self._member.chunk_addressing_method)
        md.start_chunk = chunk_id
        md.end_chunk = chunk_id
        md.data = data
        md.timestamp = int((time.time() * 1000000))

        mdata_bin = bytearray()
        mdata_bin[0:4] = struct.pack('>I', self._member.remote_channel)
        mdata_bin[4:] = md.BuildBinaryMessage()

        self._member.SendAndAccount(mdata_bin)
        self._member.set_sent.add(chunk_id)

    def SendAndSchedule(self):
        """Send requested data using LEDBAT"""

        # Get lowest chunk in flight
        min_in_fligh = None
        if len(self._member.set_sent) > 0:
            min_in_fligh = min(self._member.set_sent)

        # Chunks I have and member is interested
        set_to_send = (self._swarm.set_have & self._member.set_requested) - self._member.set_sent
        num_to_send = len(set_to_send)

        if min_in_fligh is None:
            # All is acknowledged. Try to send next requested
            if num_to_send > 0:
                # We have stuff to send
                next_id = min(set_to_send)
                self._build_and_send(next_id)
                self._ret_control.appendleft(next_id)
        else:
            # We have chunks in flight. Get earliest in-flight id
            deq_front = self._ret_control[LEDBATSendRequestedChunks.WINDOWLEN-1]

            if deq_front is None:
                # Send as normal, not enough in-flight chunks
                if num_to_send > 0:
                    # We have stuff to send
                    next_id = min(set_to_send)
                    self._build_and_send(next_id)
                    self._ret_control.appendleft(next_id)
            else:
                # Check if we need to retransmit
                if min_in_fligh <= deq_front:
                    # Retransmit
                    self._build_and_send(min_in_fligh)
                    self._member._ledbat.data_loss()
                    #logging.info("Data loss. Min in flight: {}. Delay: {}"
                    #             .format(min_in_fligh, self._member._ledbat._cto / 1000000))
                else:
                    # Send as normal
                    if num_to_send > 0:
                        # We have stuff to send
                        next_id = min(set_to_send)
                        self._build_and_send(next_id)
                        self._ret_control.appendleft(next_id)

        # Check if sending still needed?
        if len(self._member.set_sent) > 0 and len(self._member.set_requested) > 0:
            self._member._sending_handle = None

        # Get delay before next send
        #delay = max([self._member._ledbat.get_delay(self._member.chunk_size), 0.01])
        delay = self._member._ledbat.get_delay(self._member.chunk_size)
        #logging.info("Delay: {}".format(delay))
        if delay <= 0:
            self._member._sending_handle = asyncio.get_event_loop().call_soon(
                self._member.SendRequestedChunks)
        else:
            self._member._sending_handle = asyncio.get_event_loop().call_later(
                delay, self._member.SendRequestedChunks)
