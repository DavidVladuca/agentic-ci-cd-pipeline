import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

public class AppHiddenTest {
    @Test
    void sumUpToOneIsOne() {
        assertEquals(1, App.sumUpTo(1));
    }

    @Test
    void sumUpToFiveIsFifteen() {
        assertEquals(15, App.sumUpTo(5));
    }

    @Test
    void sumUpToTenIsFiftyFive() {
        assertEquals(55, App.sumUpTo(10));
    }
}