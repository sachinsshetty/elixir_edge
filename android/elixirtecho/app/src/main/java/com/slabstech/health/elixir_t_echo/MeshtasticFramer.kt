package com.slabstech.health.elixir_t_echo

import java.io.ByteArrayOutputStream

class MeshtasticFramer {
    companion object {
        private const val START1: Int = 0x94
        private const val START2: Int = 0xC3
        private const val MAX_LEN = 512
    }

    private val buf = ByteArrayOutputStream()

    fun frame(payload: ByteArray): ByteArray {
        require(payload.size <= MAX_LEN) { "Payload too large: ${payload.size}" }
        val out = ByteArray(4 + payload.size)
        out[0] = START1.toByte()
        out[1] = START2.toByte()
        out[2] = ((payload.size shr 8) and 0xFF).toByte()
        out[3] = (payload.size and 0xFF).toByte()
        System.arraycopy(payload, 0, out, 4, payload.size)
        return out
    }

    fun feed(bytes: ByteArray, onPacket: (payload: ByteArray) -> Unit) {
        buf.write(bytes)
        var data = buf.toByteArray()
        var i = 0

        fun consume(n: Int) {
            val remaining = data.copyOfRange(n, data.size)
            buf.reset()
            buf.write(remaining)
            data = remaining
            i = 0
        }

        while (data.size - i >= 4) {
            if ((data[i].toInt() and 0xFF) != START1) {
                i += 1
                continue
            }
            if ((data[i + 1].toInt() and 0xFF) != START2) {
                i += 1
                continue
            }

            val len = ((data[i + 2].toInt() and 0xFF) shl 8) or (data[i + 3].toInt() and 0xFF)
            if (len <= 0 || len > MAX_LEN) {
                i += 1
                continue
            }

            val total = 4 + len
            if (data.size - i < total) break

            val payload = data.copyOfRange(i + 4, i + 4 + len)
            onPacket(payload)
            consume(i + total)
        }

        if (i > 0 && i == data.size) {
            buf.reset()
        } else if (i > 0) {
            consume(i)
        }
    }
}
