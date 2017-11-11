# coding=utf-8
# Distributed under the MIT software license, see the accompanying
# file LICENSE or http://www.opensource.org/licenses/mit-license.php.
from collections import OrderedDict
from unittest import TestCase

import pytest
from mock import Mock, MagicMock, mock

from qrl.core import logger, config
from qrl.core.Block import Block
from qrl.core.BufferedChain import BufferedChain
from qrl.core.Chain import Chain
from qrl.core.GenesisBlock import GenesisBlock
from qrl.core.State import State
from qrl.core.Transaction import StakeTransaction
from qrl.core.Wallet import Wallet
from qrl.crypto.misc import sha256
from qrl.crypto.xmss import XMSS
from tests.misc.helper import setWalletDir

logger.initialize_default(force_console_output=True)


class TestBufferedChain(TestCase):
    def __init__(self, *args, **kwargs):
        super(TestBufferedChain, self).__init__(*args, **kwargs)

    def test_create(self):
        with setWalletDir("test_wallet"):
            # FIXME: cross-dependency
            chain = Mock(spec=Chain)
            chain.height = 0
            chain.get_block = MagicMock(return_value=None)
            chain.get_last_block = MagicMock(return_value=None)
            chain.wallet = Wallet()
            cb = BufferedChain(chain)

            self.assertEqual(0, cb.height)

            tmp_block = cb.get_block(0)
            self.assertIsNone(tmp_block)
            chain.get_block.assert_called()

            tmp_block = cb.get_last_block()
            self.assertIsNone(tmp_block)

    def test_add_empty(self):
        with State() as state:
            with setWalletDir("test_wallet"):
                chain = Mock(spec=Chain)
                chain.height = 0
                chain.get_block = MagicMock(return_value=None)
                chain.wallet = Wallet()
                chain.pstate = state

                buffered_chain = BufferedChain(chain)

                b0 = buffered_chain.get_block(0)
                buffered_chain._chain.get_block.assert_called()
                self.assertIsNone(b0)

                tmp_block = Block()
                res = buffered_chain.add_block(block=tmp_block)
                self.assertFalse(res)

    def test_add_genesis(self):
        with State() as state:
            with setWalletDir("test_wallet"):
                chain = Mock(spec=Chain)
                chain.height = 0
                chain.get_block = MagicMock(return_value=None)
                chain.wallet = Wallet()
                chain.pstate = state

                buffered_chain = BufferedChain(chain)

                b0 = buffered_chain.get_block(0)
                buffered_chain._chain.get_block.assert_called()
                self.assertIsNone(b0)

                res = buffered_chain.add_block(block=GenesisBlock())
                self.assertTrue(res)

    def test_add_2(self):
        with State() as state:
            with setWalletDir("test_wallet"):
                chain = Chain(state)
                buffered_chain = BufferedChain(chain)

                xmss_height = 6
                seed = bytes([i for i in range(48)])
                xmss = XMSS(xmss_height, seed)
                slave_xmss = XMSS(xmss_height, seed)

                h0 = sha256(b'hashchain_seed')
                h1 = sha256(h0)

                genesis_block = GenesisBlock()

                res = buffered_chain.add_block(block=genesis_block)
                self.assertTrue(res)

                stake_transaction = StakeTransaction.create(activation_blocknumber=0,
                                                            xmss=xmss,
                                                            slavePK=slave_xmss.pk(),
                                                            hashchain_terminator=h1)

                # FIXME: The test needs private access.. This is an API issue
                stake_transaction._data.nonce = 1

                stake_transaction.sign(xmss)

                chain.pstate.stake_validators_tracker.add_sv(balance=100,
                                                             stake_txn=stake_transaction,
                                                             blocknumber=0)

                tmp_block = Block.create(staking_address=bytes(xmss.get_address().encode()),
                                         block_number=1,
                                         reveal_hash=h0,
                                         prevblock_headerhash=genesis_block.headerhash,
                                         transactions=[stake_transaction],
                                         duplicate_transactions=OrderedDict(),
                                         vote=[],
                                         signing_xmss=xmss,
                                         nonce=1)

                res = buffered_chain.add_block(block=tmp_block)
                self.assertTrue(res)

    @pytest.mark.skip(reason="reproduces a bug that is being fixed")
    def test_add_3(self):
        with State() as state:
            with setWalletDir("test_wallet"):
                chain = Chain(state)
                buffered_chain = BufferedChain(chain)

                xmss_height = 6
                seed = bytes([i for i in range(48)])
                xmss = XMSS(xmss_height, seed)
                slave_xmss = XMSS(xmss_height, seed)

                staking_address = bytes(xmss.get_address().encode())

                h0 = sha256(b'hashchain_seed')
                h1 = sha256(h0)
                h2 = sha256(h1)

                genesis_block = GenesisBlock()

                res = buffered_chain.add_block(block=genesis_block)
                self.assertTrue(res)

                stake_transaction = StakeTransaction.create(activation_blocknumber=0,
                                                            xmss=xmss,
                                                            slavePK=slave_xmss.pk(),
                                                            hashchain_terminator=h2)

                # FIXME: The test needs private access.. This is an API issue
                stake_transaction._data.nonce = 1
                stake_transaction.sign(xmss)

                chain.pstate.stake_validators_tracker.add_sv(balance=100,
                                                             stake_txn=stake_transaction,
                                                             blocknumber=0)

                tmp_block1 = Block.create(staking_address=staking_address,
                                          block_number=1,
                                          reveal_hash=h1,
                                          prevblock_headerhash=genesis_block.headerhash,
                                          transactions=[stake_transaction],
                                          duplicate_transactions=OrderedDict(),
                                          vote=[],
                                          signing_xmss=xmss,
                                          nonce=1)

                res = buffered_chain.add_block(block=tmp_block1)
                self.assertTrue(res)

                # Need to move forward the time to align with block times
                with mock.patch('qrl.core.ntp.getTime') as time_mock:
                    time_mock.return_value = tmp_block1.timestamp + config.dev.minimum_minting_delay

                    tmp_block2 = Block.create(staking_address=staking_address,
                                              block_number=2,
                                              reveal_hash=h0,
                                              prevblock_headerhash=tmp_block1.headerhash,
                                              transactions=[stake_transaction],
                                              duplicate_transactions=OrderedDict(),
                                              vote=[],
                                              signing_xmss=xmss,
                                              nonce=2)

                res = buffered_chain.add_block(block=tmp_block2)
                self.assertTrue(res)
