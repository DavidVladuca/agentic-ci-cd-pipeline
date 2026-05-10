import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

public class UserFormatterHiddenTest {
    @Test
    void nullUserReturnsUnknown() {
        UserFormatter formatter = new UserFormatter();

        assertEquals("UNKNOWN", formatter.displayName(null));
    }

    @Test
    void nullNameReturnsUnknown() {
        UserFormatter formatter = new UserFormatter();

        assertEquals("UNKNOWN", formatter.displayName(new User(null)));
    }

    @Test
    void blankNameReturnsUnknown() {
        UserFormatter formatter = new UserFormatter();

        assertEquals("UNKNOWN", formatter.displayName(new User("   ")));
    }
}
