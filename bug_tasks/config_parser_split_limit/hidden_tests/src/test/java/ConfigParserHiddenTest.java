import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

public class ConfigParserHiddenTest {
    @Test
    void valueMayContainColon() {
        ConfigParser parser = new ConfigParser();

        Map<String, String> result = parser.parseLine("url: http://example.com:8080");

        assertEquals("http://example.com:8080", result.get("url"));
    }

    @Test
    void missingKeyThrows() {
        ConfigParser parser = new ConfigParser();

        assertThrows(IllegalArgumentException.class, () -> parser.parseLine(":value"));
    }
}
