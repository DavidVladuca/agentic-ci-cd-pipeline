import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertTrue;

public class WordCounterTest {
    @Test
    void emptyInputProducesEmptyMap() {
        WordCounter counter = new WordCounter();

        Map<String, Integer> counts = counter.countWords("   ");

        assertTrue(counts.isEmpty());
    }
}
