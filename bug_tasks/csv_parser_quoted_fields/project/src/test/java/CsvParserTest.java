import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;

public class CsvParserTest {
    @Test
    void parsesSimpleCsvLine() {
        CsvParser parser = new CsvParser();

        assertEquals(
            List.of("alpha", "bravo", "charlie"),
            parser.parseLine("alpha,bravo,charlie")
        );
    }
}
