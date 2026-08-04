package com.superdl.launcher.textreader

object TextOcrChunker {

    private const val MAX_CHUNK_CHARS = 380

    fun split(text: String): List<String> {
        val cleaned = text.trim()
        if (cleaned.isEmpty()) return emptyList()
        if (cleaned.length <= MAX_CHUNK_CHARS) return listOf(cleaned)

        val result = mutableListOf<String>()
        var start = 0
        while (start < cleaned.length) {
            val end = (start + MAX_CHUNK_CHARS).coerceAtMost(cleaned.length)
            val slice = cleaned.substring(start, end)
            val breakAt = if (end < cleaned.length) {
                val lastStop = maxOf(
                    slice.lastIndexOf('.'),
                    slice.lastIndexOf('!'),
                    slice.lastIndexOf('?'),
                    slice.lastIndexOf('\n'),
                    slice.lastIndexOf(' ')
                )
                if (lastStop >= MAX_CHUNK_CHARS / 4) start + lastStop + 1 else end
            } else {
                end
            }
            val chunk = cleaned.substring(start, breakAt).trim()
            if (chunk.isNotBlank()) result.add(chunk)
            start = breakAt
        }
        return result.ifEmpty { listOf(cleaned) }
    }
}