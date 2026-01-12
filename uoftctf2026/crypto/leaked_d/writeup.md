# Leaked d Writeup

## Challenge Description
**Points**: 33
**Solves**: 749

"Someone leaked my d, surely generating a new key pair is safe enough."

We are given:
- `n1`: A 1024-bit RSA modulus.
- `e1 = 65537`: Public exponent for key 1.
- `d1`: Private key for key 1.
- `e2 = 6767671`: Public exponent for key 2.
- `c`: Ciphertext encrypted with key 2.

## Solution

The challenge title "Leaked d" and the description suggest that a private key `d1` was leaked, and the user tried to "generate a new key pair". However, the reused modulus `n` implies they kept `n` and only changed `e` and `d`.

In RSA, the private key `d` is the modular inverse of `e` modulo `phi(n)`.
`e * d = 1 (mod phi(n))`
`e * d - 1 = k * phi(n)`

Since we know `e1` and `d1`, we can compute `e1 * d1 - 1`, which is a multiple of `phi(n)`.
Since `phi(n) ≈ n`, we can approximate `k ≈ (e1 * d1) / n`.
By iterating a small range around this approximation, we can find the exact `phi(n)` such that it divides `e1 * d1 - 1`.

Once we have `phi(n)`, we can calculate the private key `d2` for the second key pair corresponding to `e2`:
`d2 = inverse(e2, phi(n))`

Finally, we decrypt the ciphertext `c`:
`m = c^d2 (mod n)`

### Script
```python
# Variables provided (truncated for brevity)
n = 144193...
e1 = 65537
d1 = 125740...
e2 = 6767671
c = 317035...

# Recover Phi
# e1 * d1 - 1 = k * phi
product = e1 * d1 - 1
k_approx = product // n

phi = 0
for k in range(k_approx, k_approx + 10000):
    if product % k == 0:
        phi = product // k
        # Verification to be sure
        if pow(2, phi, n) == 1:
            break

# Calculate new private key d2
d2 = pow(e2, -1, phi)

# Decrypt
m = pow(c, d2, n)
print(f"Decrypted: {m.to_bytes((m.bit_length() + 7) // 8, 'big')}")
```

### Flag
`uoftctf{1_5h0u1dv3_ju57_ch4ng3d_th3_wh013_th1ng_1n5734d}`

