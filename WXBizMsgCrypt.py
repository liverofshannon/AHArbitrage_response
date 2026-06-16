#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
企业微信消息加解密库
参考: https://developer.work.weixin.qq.com/document/path/90968
"""

import base64
import hashlib
import struct
import time

from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes


class WXBizMsgCrypt:
    def __init__(self, token: str, encoding_aes_key: str, corp_id: str):
        self.token = token
        self.corp_id = corp_id
        self.aes_key = base64.b64decode(encoding_aes_key + "=")

    # ==================== URL验证 ====================

    def VerifyURL(self, msg_signature: str, timestamp: str, nonce: str, echostr: str):
        """验证回调URL，返回 (err_code, decrypted_echostr)"""
        sign = self._sha1(self.token, timestamp, nonce, echostr)
        if sign != msg_signature:
            return -40001, ""
        try:
            plain = self._decrypt(echostr)
            return 0, plain
        except Exception:
            return -40002, ""

    # ==================== 消息解密 ====================

    def DecryptMsg(self, post_data: bytes, msg_signature: str, timestamp: str, nonce: str):
        """
        解密POST消息体
        post_data: 原始POST body (外层XML: <xml><Encrypt>...</Encrypt></xml>)
        返回 (err_code, plain_xml_str)
        """
        import defusedxml.ElementTree as ET
        try:
            root = ET.fromstring(post_data)
            encrypt_text = root.find("Encrypt").text
        except Exception:
            return -40003, ""

        sign = self._sha1(self.token, timestamp, nonce, encrypt_text)
        if sign != msg_signature:
            return -40001, ""

        try:
            plain = self._decrypt(encrypt_text)
            return 0, plain
        except Exception:
            return -40002, ""

    # ==================== 消息加密（被动回复用）====================

    def EncryptMsg(self, reply_xml: str, nonce: str, timestamp: str = None):
        """
        加密回复消息
        返回 (err_code, encrypted_xml_str)
        """
        if timestamp is None:
            timestamp = str(int(time.time()))

        encrypted = self._encrypt(reply_xml)
        sign = self._sha1(self.token, timestamp, nonce, encrypted)

        resp = (
            f"<xml>"
            f"<Encrypt><![CDATA[{encrypted}]]></Encrypt>"
            f"<MsgSignature><![CDATA[{sign}]]></MsgSignature>"
            f"<TimeStamp>{timestamp}</TimeStamp>"
            f"<Nonce><![CDATA[{nonce}]]></Nonce>"
            f"</xml>"
        )
        return 0, resp

    # ==================== 内部方法 ====================

    def _sha1(self, *args):
        return hashlib.sha1("".join(sorted(args)).encode()).hexdigest()

    def _decrypt(self, encrypted_str: str) -> str:
        iv = self.aes_key[:16]
        cipher = AES.new(self.aes_key, AES.MODE_CBC, iv)
        raw = cipher.decrypt(base64.b64decode(encrypted_str))
        pad = raw[-1]
        content = raw[16:-pad]  # 去除前16字节随机数 + 尾部填充
        content_len = struct.unpack(">I", content[:4])[0]
        return content[4:4 + content_len].decode("utf-8")

    def _encrypt(self, text: str) -> str:
        random_bytes = get_random_bytes(16)
        text_bytes = text.encode("utf-8")
        msg_len = struct.pack(">I", len(text_bytes))
        corp_bytes = self.corp_id.encode("utf-8")
        raw = random_bytes + msg_len + text_bytes + corp_bytes

        block_size = 32
        pad_len = block_size - (len(raw) % block_size)
        raw += bytes([pad_len] * pad_len)

        iv = self.aes_key[:16]
        cipher = AES.new(self.aes_key, AES.MODE_CBC, iv)
        return base64.b64encode(cipher.encrypt(raw)).decode()
