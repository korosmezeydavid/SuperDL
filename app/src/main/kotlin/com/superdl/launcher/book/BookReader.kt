package com.superdl.launcher.book

import android.content.Context
import com.superdl.launcher.tts.TtsManager

class BookReader(
    private val context: Context,
    private val tts: TtsManager,
    private val onProgress: (chunkIndex: Int, totalChunks: Int, charOffset: Int) -> Unit,
    private val onFinished: () -> Unit,
    private val onError: (String) -> Unit
) {
    private var chunks: List<String> = emptyList()
    private var chunkOffsets: IntArray = intArrayOf()
    private var chunkIndex: Int = 0
    private var book: BookEntry? = null
    private var bookTitle: String = ""
    private var running = false
    private var paused = false
    private var fullText: String = ""

    val isActive: Boolean get() = running
    val isPaused: Boolean get() = paused

    fun currentCharOffset(): Int =
        chunkOffsets.getOrNull(chunkIndex) ?: 0

    fun currentPreview(): String =
        chunks.getOrNull(chunkIndex)?.take(120).orEmpty()

    fun progressPercent(): Int {
        if (fullText.isEmpty()) return 0
        return ((currentCharOffset().toDouble() / fullText.length) * 100).toInt().coerceIn(0, 100)
    }

    fun start(entry: BookEntry, startOffset: Int = 0) {
        stop()
        book = entry
        running = true
        paused = false
        val cacheFile = BookLibrary.materializeToCache(context, entry)
            ?: run {
                onError("A könyv fájlja nem nyitható meg.")
                running = false
                return
            }
        val extracted = BookTextExtractor.extract(context, cacheFile).getOrElse { err ->
            onError(err.message ?: "A könyv szövege nem olvasható.")
            running = false
            return
        }
        beginReading(entry, extracted.title.ifBlank { entry.title }, extracted.text, startOffset)
    }

    fun startWithText(entry: BookEntry, title: String, text: String, startOffset: Int = 0) {
        stop()
        beginReading(entry, title.ifBlank { entry.title }, text, startOffset)
    }

    private fun beginReading(entry: BookEntry, title: String, text: String, startOffset: Int) {
        book = entry
        running = true
        paused = false
        bookTitle = title
        fullText = text
        if (fullText.isBlank()) {
            onError("A könyv üres vagy nem tartalmaz felolvasható szöveget.")
            running = false
            return
        }
        buildChunks(fullText)
        chunkIndex = offsetToChunkIndex(startOffset.coerceIn(0, fullText.length))
        BookStore.touchRecent(context, entry.path)
        speakCurrentChunk()
    }

    fun pause() {
        if (!running || paused) return
        paused = true
        tts.stop()
    }

    fun resume() {
        if (!running || !paused) return
        paused = false
        speakCurrentChunk()
    }

    fun stop() {
        running = false
        paused = false
        tts.stop()
        book?.let { BookStore.savePosition(context, it.path, currentCharOffset()) }
        book = null
        chunks = emptyList()
        chunkOffsets = intArrayOf()
        chunkIndex = 0
        fullText = ""
        bookTitle = ""
    }

    fun repeatChunk() {
        if (!running || paused) return
        tts.stop()
        speakCurrentChunk()
    }

    fun nextChunk() {
        if (!running || chunks.isEmpty()) return
        if (chunkIndex >= chunks.lastIndex) {
            finishReading()
            return
        }
        tts.stop()
        chunkIndex++
        paused = false
        speakCurrentChunk()
    }

    fun prevChunk() {
        if (!running || chunks.isEmpty()) return
        tts.stop()
        chunkIndex = (chunkIndex - 1).coerceAtLeast(0)
        paused = false
        speakCurrentChunk()
    }

    fun jumpToOffset(offset: Int) {
        if (!running || fullText.isEmpty()) return
        tts.stop()
        chunkIndex = offsetToChunkIndex(offset.coerceIn(0, fullText.length))
        paused = false
        speakCurrentChunk()
    }

    fun addBookmark(): BookBookmark? {
        val currentBook = book ?: return null
        return BookStore.addBookmark(
            context = context,
            bookPath = currentBook.path,
            bookTitle = bookTitle,
            charOffset = currentCharOffset(),
            preview = currentPreview()
        )
    }

    private fun buildChunks(text: String) {
        val maxLen = 700
        val result = mutableListOf<String>()
        val offsets = mutableListOf<Int>()
        var start = 0
        while (start < text.length) {
            offsets.add(start)
            val end = (start + maxLen).coerceAtMost(text.length)
            val slice = text.substring(start, end)
            val breakAt = if (end < text.length) {
                val lastStop = maxOf(
                    slice.lastIndexOf('.'),
                    slice.lastIndexOf('!'),
                    slice.lastIndexOf('?'),
                    slice.lastIndexOf('\n')
                )
                if (lastStop >= maxLen / 3) start + lastStop + 1 else end
            } else end
            val chunk = text.substring(start, breakAt).trim()
            if (chunk.isNotBlank()) result.add(chunk)
            start = breakAt
        }
        if (result.isEmpty()) {
            result.add(text)
            offsets.add(0)
        }
        chunks = result
        chunkOffsets = offsets.toIntArray()
    }

    private fun offsetToChunkIndex(offset: Int): Int {
        if (chunkOffsets.isEmpty()) return 0
        var best = 0
        for (i in chunkOffsets.indices) {
            if (chunkOffsets[i] <= offset) best = i else break
        }
        return best
    }

    private fun speakCurrentChunk() {
        if (!running || paused) return
        val chunk = chunks.getOrNull(chunkIndex) ?: run {
            finishReading()
            return
        }
        onProgress(chunkIndex, chunks.size, currentCharOffset())
        tts.speakThen(chunk) {
            if (!running || paused) return@speakThen
            if (chunkIndex >= chunks.lastIndex) {
                finishReading()
            } else {
                chunkIndex++
                speakCurrentChunk()
            }
        }
    }

    private fun finishReading() {
        book?.let { BookStore.savePosition(context, it.path, currentCharOffset()) }
        running = false
        paused = false
        onFinished()
    }
}