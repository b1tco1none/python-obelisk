import struct
from decimal import Decimal

from twisted.internet import reactor

from zmqbase import to_btc, btc, age
from zmqbase import ClientBase, checksum, MAX_UINT32

from btclib import to_hash160, to_addr, BlockHeader

import models
import serialize
import error_code

def unpack_error(data):
    value = struct.unpack_from('<I', data, 0)[0]
    return error_code.error_code.name_from_id(value)

def pack_block_index(index):
    if type(index) == str:
        assert len(index) == 32
        return serialize.ser_hash(index)
    elif type(index) == int:
        return struct.pack('<I', index)
    else:
        raise ValueError("Unknown index type")

class ObeliskOfLightClient(ClientBase):
    valid_messages = ['fetch_block_header', 'fetch_history', 'subscribe',
        'fetch_last_height', 'fetch_transaction', 'fetch_spend',
        'fetch_transaction_index', 'fetch_block_transaction_hashes',
        'fetch_block_height', 'update', 'renew']

    subscribed = 0
    # Command implementations
    def renew_address(self, address):
        # prepare parameters
        data = struct.pack('B', 0)          # address version
        data += address[::-1]               # address

        # run command
        self.send_command('address.renew', data)
        # renew triggered again on response
        reactor.callLater(120, self.renew_address, address)

    def subscribe_address(self, address):
        # prepare parameters
        data = struct.pack('B', 0)          # address version
        data += address[::-1]               # address

        # run command
        self.send_command('address.subscribe', data)
        reactor.callLater(120, self.renew_address, address)

    def fetch_block_header(self, index, cb):
        data = pack_block_index(index)
        self.send_command('blockchain.fetch_block_header', data, cb)

    def fetch_history(self, address, cb):
        # prepare parameters
        data = struct.pack('B', 0)          # address version
        data += address[::-1]               # address
        data += struct.pack('<I', 0)        # from_height

        # run command
        self.send_command('address.fetch_history', data, cb)

    def fetch_last_height(self, cb):
        self.send_command('blockchain.fetch_last_height', cb=cb)

    def fetch_transaction(self, tx_hash, cb):
        data = serialize.ser_hash(tx_hash)
        self.send_command('blockchain.fetch_transaction', data, cb)

    def fetch_spend(self, outpoint, cb):
        data = outpoint.serialize()
        self.send_command('blockchain.fetch_spend', data, cb)

    def fetch_transaction_index(self, tx_hash, cb):
        data = serialize.ser_hash(tx_hash)
        self.send_command('blockchain.fetch_transaction_index', data, cb)

    def fetch_block_transaction_hashes(self, index, cb):
        data = pack_block_index(index)
        self.send_command('blockchain.fetch_block_transaction_hashes',
            data, cb)

    def fetch_block_height(self, blk_hash, cb):
        data = serialize.ser_hash(blk_hash)
        self.send_command('blockchain.fetch_block_height', data, cb)

    # receive handlers
    def on_fetch_block_header(self, data):
        error = unpack_error(data)
        assert len(data[4:]) == 80
        header = BlockHeader.deserialize(data[4:])
        return (error, header)

    def on_fetch_history(self, data):
        error = unpack_error(data)
        # parse results
        rows = self.unpack_table("<32sIIQ32sII", data, 4)
        return (error, rows)

    def on_fetch_last_height(self, data):
        error = unpack_error(data)
        height = struct.unpack('<I', data[4:])[0]
        return (error, height)

    def on_fetch_transaction(self, data):
        error = unpack_error(data)
        tx = serialize.deser_tx(data[4:])
        return (error, tx)

    def on_fetch_spend(self, data):
        error = unpack_error(data)
        spend = serialize.deser_output_point(data[4:])
        return (error, spend)

    def on_fetch_transaction_index(self, data):
        error = unpack_error(data)
        height, index = struct.unpack("<II", data[4:])
        return (error, height, index)

    def on_fetch_block_transaction_hashes(self, data):
        error = unpack_error(data)
        rows = self.unpack_table("32s", data, 4)
        hashes = [row[0][::-1] for row in rows]
        return (error, hashes)

    def on_fetch_block_height(self, data):
        error = unpack_error(data)
        height = struct.unpack('<I', data[4:])[0]
        return (error, height)
        
    def on_subscribe(self, data):
        self.subscribed += 1
        error = unpack_error(data)
        if error:
            print "Error subscribing"
        if not self.subscribed%1000:
            print "Subscribed ok", self.subscribed

    def on_update(self, data):
        print "Update for address"

    def on_renew(self, data):
        self.subscribed += 1
        error = unpack_error(data)
        if error:
            print "Error subscribing"
        if not self.subscribed%1000:
            print "Renew ok", self.subscribed

