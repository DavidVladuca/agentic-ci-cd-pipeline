import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

public class UserFormatterTest {
    @Test
    void formatsNormalName() {
        UserFormatter formatter = new UserFormatter();

        assertEquals("ALICE", formatter.displayName(new User(" alice ")));
    }
}
