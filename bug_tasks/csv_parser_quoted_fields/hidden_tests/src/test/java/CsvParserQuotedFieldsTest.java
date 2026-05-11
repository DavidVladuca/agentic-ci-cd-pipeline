import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;

public class CsvParserQuotedFieldsTest {
    @Test
    void quotedFieldMayContainComma() {
        CsvParser parser = new CsvParser();

        assertEquals(
            List.of("alpha", "bravo,charlie", "delta"),
            parser.parseLine("alpha,\"bravo,charlie\",delta")
        );
    }

    @Test
    void escapedQuotesInsideQuotedFieldAreUnescaped() {
        CsvParser parser = new CsvParser();

        assertEquals(
            List.of("a \"quoted\" value", "x"),
            parser.parseLine("\"a \"\"quoted\"\" value\",x")
        );
    }

    @Test
    void trailingEmptyFieldIsPreserved() {
        CsvParser parser = new CsvParser();

        assertEquals(
            List.of("alpha", "bravo", ""),
            parser.parseLine("alpha,bravo,")
        );
    }
}
