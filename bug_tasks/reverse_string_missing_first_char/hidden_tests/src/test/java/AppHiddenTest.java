import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

public class AppHiddenTest {
    @Test
    void reversesThreeCharacters() {
        assertEquals("cba", App.reverse("abc"));
    }

    @Test
    void reversesHello() {
        assertEquals("olleh", App.reverse("hello"));
    }

    @Test
    void reversesSingleCharacter() {
        assertEquals("x", App.reverse("x"));
    }
}