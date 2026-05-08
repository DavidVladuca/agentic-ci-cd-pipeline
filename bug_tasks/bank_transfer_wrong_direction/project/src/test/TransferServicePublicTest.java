import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

public class TransferServicePublicTest {
    @Test
    void accountDepositIncreasesBalance() {
        Account account = new Account(10);

        account.deposit(5);

        assertEquals(15, account.getBalance());
    }

    @Test
    void accountWithdrawDecreasesBalance() {
        Account account = new Account(10);

        account.withdraw(4);

        assertEquals(6, account.getBalance());
    }

    @Test
    void nullAccountsThrow() {
        TransferService service = new TransferService();
        Account account = new Account(10);

        assertThrows(IllegalArgumentException.class, () -> service.transfer(null, account, 1));
        assertThrows(IllegalArgumentException.class, () -> service.transfer(account, null, 1));
    }
}