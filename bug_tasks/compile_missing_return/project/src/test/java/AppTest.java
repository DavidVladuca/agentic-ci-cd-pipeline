import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

public class AppTest {
    @Test
    void positiveValueIsPositive() {
        assertEquals("positive", App.sign(7));
    }
}
