import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;

public class ConfigParserTest {
    @Test
    void parsesSimpleKeyValue() {
        ConfigParser parser = new ConfigParser();

        Map<String, String> result = parser.parseLine("host: localhost");

        assertEquals("localhost", result.get("host"));
    }
}
