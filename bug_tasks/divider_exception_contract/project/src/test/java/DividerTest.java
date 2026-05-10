import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

public class DividerTest {
    @Test
    void dividesNormalValues() {
        Divider divider = new Divider();

        assertEquals(4, divider.divide(8, 2));
    }
}
