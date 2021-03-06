import numpy as np
from copy import deepcopy

from config import Config


def bitwise_xor_bytes(a, b):
    result_int = int.from_bytes(a, byteorder="big") ^ int.from_bytes(b, byteorder="big")
    return result_int.to_bytes(max(len(a), len(b)), byteorder="big")


class Verifier:

    def __init__(self):
        self.gfbase = 29
        self.gfbound = 2 ** 8
        self.gfilog = self._gfilog()
        self.gflog = self._gflog()
        self.p_id = Config.SN - 2
        self.q_id = Config.SN - 1

    def recover(self, broken_storage_ids, all_contents: dict):
        assert len(broken_storage_ids) <= 2
        new_contents = deepcopy(all_contents)
        coeffs = []

        # get coefficients of data storages
        for st_id in range(Config.SS):
            coeffs.append(self.gfilog[st_id])

        # only one storage corrupted
        if len(broken_storage_ids) == 1:
            broken_id = broken_storage_ids[0]
            # data storage
            if broken_id < Config.SS:
                self._recover_data_from_p(broken_id, new_contents)
                # self._recover_data_from_q(broken_id,new_contents,coeffs)
            # P storage
            elif broken_id == self.p_id:
                self._recover_p(new_contents)
            # Q storage
            elif broken_id == self.q_id:
                self._recover_q(new_contents, coeffs)
        # two storage corrupted
        elif len(broken_storage_ids) == 2:
            # P storage and Q storages
            if self.p_id in broken_storage_ids and self.q_id in broken_storage_ids:
                self._recover_p(new_contents)
                self._recover_q(new_contents, coeffs)
            # data storage and P storage
            elif self.p_id in broken_storage_ids and self.q_id not in broken_storage_ids:
                data_id = min(broken_storage_ids)
                self._recover_data_from_q(data_id, new_contents, coeffs)
                self._recover_p(new_contents)
            # data storage and Q storage
            elif self.q_id in broken_storage_ids and self.p_id not in broken_storage_ids:
                data_id = min(broken_storage_ids)
                self._recover_data_from_p(data_id, new_contents)
                self._recover_q(new_contents, coeffs)
            # two data storage
            elif self.q_id not in broken_storage_ids and self.p_id not in broken_storage_ids:
                coeff_a = coeffs[broken_storage_ids[0]]
                coeff_b = coeffs[broken_storage_ids[1]]
                for blk_id in range(Config.BN):
                    recover_a = b''
                    recover_b = b''
                    for i in range(Config.BS):
                        data_a = b'\x00'
                        data_b = b'\x00'
                        for j in range(Config.SS):
                            if j not in broken_storage_ids:
                                data_a = bitwise_xor_bytes(data_a, bytes([new_contents[(j, blk_id)][0][i]]))
                                data_b = bitwise_xor_bytes(data_b,
                                                           self._gf_product(bytes([new_contents[(j, blk_id)][0][i]]),
                                                                            coeffs[j]))
                                data_b = bitwise_xor_bytes(data_b,
                                                           self._gf_product(bytes([new_contents[(j, blk_id)][0][i]]),
                                                                            coeff_a))
                        data_b = bitwise_xor_bytes(data_b,
                                                   self._gf_product(bytes([new_contents[(self.p_id, blk_id)][0][i]]),
                                                                    coeff_a))
                        data_b = bitwise_xor_bytes(data_b, bytes([new_contents[(self.q_id, blk_id)][0][i]]))
                        data_b = self._gf_div(data_b, bitwise_xor_bytes(bytes([coeff_a]), bytes([coeff_b])))
                        recover_b += data_b

                        data_a = bitwise_xor_bytes(data_a, data_b)
                        data_a = bitwise_xor_bytes(data_a, bytes([new_contents[(self.p_id, blk_id)][0][i]]))
                        recover_a += data_a

                    new_contents[(broken_storage_ids[0], blk_id)] = [recover_a]
                    new_contents[(broken_storage_ids[1], blk_id)] = [recover_b]

        return new_contents

    def _recover_p(self, contents):
        for blk_id in range(Config.BN):
            recover_block = b''
            for i in range(Config.BS):
                p_check = b'\x00'
                for j in range(Config.SS):
                    p_check = bitwise_xor_bytes(p_check, bytes([contents[(j, blk_id)][0][i]]))
                recover_block += p_check
            contents[(self.p_id, blk_id)] = [recover_block]

    def _recover_q(self, contents, coeffs):
        for blk_id in range(Config.BN):
            recover_block = b''
            for i in range(Config.BS):
                q_check = b'\x00'
                for j in range(Config.SS):
                    q_check = bitwise_xor_bytes(q_check,
                                                self._gf_product(bytes([contents[(j, blk_id)][0][i]]), coeffs[j]))
                recover_block += q_check
            contents[(self.q_id, blk_id)] = [recover_block]

    def _recover_data_from_p(self, data_id, contents):
        for blk_id in range(Config.BN):
            recover_block = b''
            for i in range(Config.BS):
                data = b'\x00'
                for j in range(Config.SS):
                    if j != data_id:
                        data = bitwise_xor_bytes(data, bytes([contents[(j, blk_id)][0][i]]))
                data = bitwise_xor_bytes(data, bytes([contents[(self.p_id, blk_id)][0][i]]))
                recover_block += data
            contents[(data_id, blk_id)] = [recover_block]

    def _recover_data_from_q(self, data_id, contents, coeffs):
        for blk_id in range(Config.BN):
            recover_block = b''
            for i in range(Config.BS):
                data = b'\x00'
                for j in range(Config.SS):
                    if j != data_id:
                        data = bitwise_xor_bytes(data,
                                                 self._gf_product(bytes([contents[(j, blk_id)][0][i]]), coeffs[j]))
                data = bitwise_xor_bytes(data, bytes([contents[(self.q_id, blk_id)][0][i]]))
                data = self._gf_div(data, coeffs[data_id])
                recover_block += data
            contents[(data_id, blk_id)] = [recover_block]

    def _gfilog(self):
        ilog = np.empty(self.gfbound, dtype=np.uint8)
        for idx in range(self.gfbound - 1):
            ilog[idx] = self.coefficient(idx)
        return ilog

    def _gflog(self):
        log = np.empty(self.gfbound, dtype=np.uint8)
        for idx in range(self.gfbound):
            log[int(self.gfilog[idx])] = idx
        return log

    def _gf_product(self, x, coeff):
        if isinstance(x, bytes):
            x = int.from_bytes(x, byteorder="big")
        if isinstance(coeff, bytes):
            coeff = int.from_bytes(coeff, byteorder="big")

        if x == 0 or coeff == 0:
            return bytes([0])
        else:
            return bytes([self.gfilog[int((int(self.gflog[x]) + int(self.gflog[coeff])) % 255)]])

    def _gf_div(self, x, coeff):
        if isinstance(x, bytes):
            x = int.from_bytes(x, byteorder="big")
        if isinstance(coeff, bytes):
            coeff = int.from_bytes(coeff, byteorder="big")
        if x == 0 or coeff == 0:
            return bytes([0])
        else:
            return bytes([self.gfilog[(int(self.gflog[x]) - int(self.gflog[coeff])) % 255]])

    def coefficient(self, index):
        if 2 ** index < self.gfbound:
            return 2 ** index
        elif 2 ** index >= self.gfbound:
            coeff = 2 * self.coefficient(index - 1)
            if coeff < self.gfbound:
                return coeff
            else:
                return coeff ^ self.gfbound ^ self.gfbase

    def parties_renew(self, contents, test=False):
        if not test:

            for c_i in range(len(contents)):
                assert len(contents[c_i][0]) == Config.BS

        blocks = list()
        coeffs = list()
        assert len(contents) == Config.SS  # this line need to be modified when some storage shutdown
        for st_id in range(Config.SS):
            # blocks.append(storages[st_id].read(block_id))  # contents
            blocks.append(contents[st_id][0])
            coeffs.append(self.gfilog[st_id])

        p_block = b''
        q_block = b''
        for i in range(Config.BS):
            p_check = b'\x00'
            q_check = b'\x00'
            for j in range(Config.SS):
                data = bytes([blocks[j][i]])
                p_check = bitwise_xor_bytes(p_check, data)
                q_check = bitwise_xor_bytes(q_check, self._gf_product(data, coeffs[j]))
            p_block += p_check
            q_block += q_check

        return p_block, q_block  # contents


if __name__ == '__main__':
    # a = b'\x00?\x00\x00PK\x03\x04\x14\x00\x06\x00\x08\x00\x00\x00!\x002\x91oWf\x01\x00\x00\xa5\x05\x00\x00\x13\x00\x08\x02[Content_Types].xml \xa2\x04\x02(\xa0\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    # b = b'l\x03\x00\x00\xc2\xd1&L/I\xfe\x04\x00\x00\xff\xff\x03\x00PK\x01\x02-\x00\x14\x00\x06\x00\x08\x00\x00\x00!\x002\x91oWf\x01\x00\x00\xa5\x05\x00\x00\x13\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00[Content_Types].xml'
    a = b'\x00'
    b = b'l'
    Config.BS = len(a)
    Config.SN = 4
    Config.SS = 2
    Config.BN = 1

    check_error = Verifier()
    p, q = check_error.parties_renew([[a], [b]], True)

    print(p.hex())
    print(q.hex())

    all_dic = {(2, 0): [p], (3, 0): [q]}

    new_content = check_error.recover([0, 1], all_dic)

    print(new_content)
