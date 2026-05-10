import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;

public class WordCounterHiddenTest {
    @Test
    void countsRepeatedWords() {
        WordCounter counter = new WordCounter();

        Map<String, Integer> counts = counter.countWords("red blue red");

        assertEquals(2, counts.get("red"));
        assertEquals(1, counts.get("blue"));
    }

    @Test
    void splitsOnMultipleWhitespaceCharacters() {
        WordCounter counter = new WordCounter();

        Map<String, Integer> counts = counter.countWords("red   blue\nred");

        assertEquals(2, counts.get("red"));
        assertEquals(1, counts.get("blue"));
    }
}
