import time
import random

class BlackjackShoe:
    def __init__(self, num_decks=8, penetration_limit=0.75):
        self.num_decks = num_decks
        self.penetration_limit = penetration_limit
        self.reset_shoe()
        
    def reset_shoe(self):
        """Menginisialisasi shoe standar kasino dengan gabungan 8 dek kartu."""
        # Setiap rank 2-9 memiliki 4 kartu per dek. Rank 10 (10, J, Q, K) memiliki 16 kartu per dek. Ace memiliki 4 kartu.
        self.initial_cards = {
            2: 4 * self.num_decks,
            3: 4 * self.num_decks,
            4: 4 * self.num_decks,
            5: 4 * self.num_decks,
            6: 4 * self.num_decks,
            7: 4 * self.num_decks,
            8: 4 * self.num_decks,
            9: 4 * self.num_decks,
            10: 16 * self.num_decks, # 10, J, Q, K digabung karena nilainya sama
            11: 4 * self.num_decks   # Ace diinisialisasi dengan nilai dasar 11
        }
        self.cards = self.initial_cards.copy()
        self.total_cards = sum(self.cards.values())
        self.cards_dealt = 0
        self.running_count = 0

    def get_remaining_cards_count(self):
        return sum(self.cards.values())

    def get_remaining_decks(self):
        # Estimasi sisa dek presisi untuk pembagi True Count
        rem = self.get_remaining_cards_count() / 52.0
        return max(rem, 0.1) # Cegah pembagian dengan nol

    def get_true_count(self):
        return self.running_count / self.get_remaining_decks()

    def update_count(self, card_value):
        """Sistem Penghitungan Kartu Hi-Lo Standar [Batasan E]"""
        if 2 <= card_value <= 6:
            self.running_count += 1
        elif card_value in [10, 11]:
            self.running_count -= 1

    def deal_card(self):
        """Menarik satu kartu dan memicu reshuffle otomatis pada batas penetrasi 75% [Batasan D]"""
        if self.cards_dealt >= self.total_cards * self.penetration_limit:
            print("[Sistem Shoe] Batas Penetrasi 75% tercapai. Melakukan Reshuffle Dek...")
            self.reset_shoe()
            
        available_cards = [card for card, count in self.cards.items() if count > 0]
        if not available_cards:
            self.reset_shoe()
            available_cards = [card for card, count in self.cards.items() if count > 0]
            
        card = random.choice(available_cards)
        self.cards[card] -= 1
        self.cards_dealt += 1
        self.update_count(card)
        return card

    def set_custom_shoe(self, remaining_decks, desired_true_count):
        """Metode pembantu untuk memanipulasi sisa kartu di shoe demi keperluan simulasi benchmark."""
        self.cards = {
            2: int(4 * remaining_decks),
            3: int(4 * remaining_decks),
            4: int(4 * remaining_decks),
            5: int(4 * remaining_decks),
            6: int(4 * remaining_decks),
            7: int(4 * remaining_decks),
            8: int(4 * remaining_decks),
            9: int(4 * remaining_decks),
            10: int(16 * remaining_decks),
            11: int(4 * remaining_decks)
        }
        # True Count positif berarti sisa dek memiliki konsentrasi kartu besar yang lebih tinggi
        target_deficit = int(desired_true_count * remaining_decks)
        for _ in range(abs(target_deficit)):
            small_ranks = [r for r in range(2, 7) if self.cards[r] > 0]
            large_ranks = [10, 11]
            if target_deficit > 0 and small_ranks:
                sr = random.choice(small_ranks)
                lr = random.choice(large_ranks)
                self.cards[sr] -= 1
                self.cards[lr] += 1
                
        rem_total = sum(self.cards.values())
        self.cards_dealt = (8 * 52) - rem_total
        self.running_count = int(desired_true_count * (rem_total / 52.0))


class BlackjackState:
    """Menyimpan representasi snapshot state permainan saat pengujian keputusan dilakukan [Batasan B]"""
    def __init__(self, player_total, dealer_upcard, true_count, is_player_soft=False):
        self.player_total = player_total
        self.dealer_upcard = dealer_upcard
        self.true_count = true_count
        self.is_player_soft = is_player_soft


# --- DEKLARASI FUNGSI KOMPUTASI KEPUTASAN GLOBAL ---

def add_card_points(total, has_soft_ace, card):
    """Menghitung total poin dengan logika konversi nilai Ace dari 11 menjadi 1 saat bust."""
    if card == 11:
        total += 11
        has_soft_ace += 1
    else:
        total += card
    while total > 21 and has_soft_ace > 0:
        total -= 10
        has_soft_ace -= 1
    return total, has_soft_ace


def evaluate_final_payout(player_total, dealer_total):
    """Menentukan nilai utilitas akhir (1 untuk menang, -1 kalah, 0 seri)."""
    if dealer_total > 21:
        return 1.0  # Dealer bust
    if player_total > dealer_total:
        return 1.0  # Pemain menang skor
    if player_total < dealer_total:
        return -1.0 # Dealer menang skor
    return 0.0     # Push (Seri)


# --- LOGIKA REKURSIF DAN TRANSISI UNTUK DP ---

def get_dealer_dist_dp(d_total, d_soft, card_counts, memo):
    """Menghitung probabilitas terminal sebaran nilai dealer secara pemrograman dinamis."""
    counts_tuple = tuple(sorted(card_counts.items()))
    state_key = (d_total, d_soft, counts_tuple)
    if state_key in memo:
        return memo[state_key]
        
    # Aturan Dealer [Batasan F]: Wajib Stand jika >= 17
    if d_total >= 17:
        return {d_total: 1.0}
        
    total_cards = sum(card_counts.values())
    if total_cards == 0:
        return {d_total: 1.0}
        
    merged_dist = {}
    for v, count in card_counts.items():
        if count > 0:
            prob = count / total_cards
            new_d_total, new_d_soft = add_card_points(d_total, d_soft, v)
            
            next_counts = card_counts.copy()
            next_counts[v] -= 1
            
            sub_dist = get_dealer_dist_dp(new_d_total, new_d_soft, next_counts, memo)
            for score, p_score in sub_dist.items():
                merged_dist[score] = merged_dist.get(score, 0.0) + prob * p_score
                
    memo[state_key] = merged_dist
    return merged_dist


def get_ev_hit_dp(p_total, p_soft, d_upcard, card_counts_tuple, memo, dealer_memo):
    """Mengestimasi Nilai Ekspektasi Termahal untuk keputusan HIT beruntun."""
    state_key = (p_total, p_soft, card_counts_tuple)
    if state_key in memo:
        return memo[state_key]
        
    card_counts = dict(card_counts_tuple)
    total_cards = sum(card_counts.values())
    if total_cards == 0:
        return 0.0
        
    ev = 0.0
    for v, count in card_counts.items():
        if count > 0:
            prob = count / total_cards
            new_ptotal, new_psoft = add_card_points(p_total, p_soft, v)
            
            if new_ptotal > 21:
                # Logika Pruning internal: Jika bust otomatis bernilai negatif penuh
                ev += prob * (-1.0)
            else:
                next_counts = card_counts.copy()
                next_counts[v] -= 1
                next_counts_tuple = tuple(sorted(next_counts.items()))
                
                # Hitung EV untuk aksi STAND di simpul masa depan
                d_soft_init = 1 if d_upcard == 11 else 0
                d_dist = get_dealer_dist_dp(d_upcard, d_soft_init, next_counts, dealer_memo)
                ev_s = sum(p * evaluate_final_payout(new_ptotal, dt) for dt, p in d_dist.items())
                
                # Hitung EV untuk aksi HIT lagi secara rekursif
                ev_h = get_ev_hit_dp(new_ptotal, new_psoft, d_upcard, next_counts_tuple, memo, dealer_memo)
                
                # Persamaan Bellman Maksimalisasi Keputusan [Batasan A]
                ev += prob * max(ev_s, ev_h)
                
    memo[state_key] = ev
    return ev


# --- LOGIKA DFS UNTUK BACKTRACKING PURE ---

def backtrack_dealer_dfs(d_total, d_soft, card_counts, current_prob, depth, max_depth):
    """Penelusuran murni pohon permutasi kartu dealer tanpa tabel memoisasi."""
    if d_total >= 17 or depth >= max_depth:
        return {d_total: current_prob}
        
    total_cards = sum(card_counts.values())
    if total_cards == 0:
        return {d_total: current_prob}
        
    res_dist = {}
    for v, count in card_counts.items():
        if count > 0:
            prob = count / total_cards
            new_total, new_soft = add_card_points(d_total, d_soft, v)
            
            next_counts = card_counts.copy()
            next_counts[v] -= 1
            
            sub_dist = backtrack_dealer_dfs(new_total, new_soft, next_counts, current_prob * prob, depth + 1, max_depth)
            for score, p_score in sub_dist.items():
                res_dist[score] = res_dist.get(score, 0.0) + p_score
    return res_dist


def backtrack_player_hit_dfs(p_total, p_soft, d_upcard, card_counts, depth, max_depth):
    """Mengeksplorasi seluruh kombinasi secara DFS murni dengan Pruning eksplisit jika bust."""
    if p_total > 21:
        return -1.0 # Mekanisme Pruning ketika Nilai Akumulasi Kartu Pemain Bust (>21)
        
    if depth >= max_depth:
        # Batasan kedalaman buatan untuk mencegah overhead ledakan kombinatorial pada demo
        d_soft_init = 1 if d_upcard == 11 else 0
        d_dist = backtrack_dealer_dfs(d_upcard, d_soft_init, card_counts, 1.0, 0, max_depth=3)
        return sum(p * evaluate_final_payout(p_total, dt) for dt, p in d_dist.items())
        
    total_cards = sum(card_counts.values())
    if total_cards == 0:
        return 0.0
        
    ev = 0.0
    for v, count in card_counts.items():
        if count > 0:
            prob = count / total_cards
            new_ptotal, new_psoft = add_card_points(p_total, p_soft, v)
            
            if new_ptotal > 21:
                ev += prob * (-1.0) # Cabang dipangkas dari eksplorasi DFS lebih dalam
            else:
                next_counts = card_counts.copy()
                next_counts[v] -= 1
                
                d_soft_init = 1 if d_upcard == 11 else 0
                d_dist = backtrack_dealer_dfs(d_upcard, d_soft_init, next_counts, 1.0, 0, max_depth=3)
                ev_s = sum(p * evaluate_final_payout(new_ptotal, dt) for dt, p in d_dist.items())
                
                ev_h = backtrack_player_hit_dfs(new_ptotal, new_psoft, d_upcard, next_counts, depth + 1, max_depth)
                ev += prob * max(ev_s, ev_h)
    return ev


class BlackjackSolver:
    @staticmethod
    def solve_via_dynamic_programming(shoe, player_total, dealer_upcard):
        """Menghitung Nilai Ekspektasi dengan pendekatan Rekursi + Memoisasi (DP)."""
        card_counts = shoe.cards.copy()
        d_soft_init = 1 if dealer_upcard == 11 else 0
        
        dealer_memo = {}
        d_dist = get_dealer_dist_dp(dealer_upcard, d_soft_init, card_counts, dealer_memo)
        ev_stand = sum(p * evaluate_final_payout(player_total, dt) for dt, p in d_dist.items())
        
        counts_tuple = tuple(sorted(card_counts.items()))
        dp_memo = {}
        ev_hit = get_ev_hit_dp(player_total, 0, dealer_upcard, counts_tuple, dp_memo, dealer_memo)
        
        recommendation = "STAND" if ev_stand >= ev_hit else "HIT"
        return recommendation, max(ev_stand, ev_hit)

    @staticmethod
    def solve_via_backtracking(shoe, player_total, dealer_upcard):
        """Menghitung rekomendasi keputusan menggunakan penelusuran DFS pohon state murni."""
        card_counts = shoe.cards.copy()
        d_soft_init = 1 if dealer_upcard == 11 else 0
        
        d_dist = backtrack_dealer_dfs(dealer_upcard, d_soft_init, card_counts, 1.0, depth=0, max_depth=3)
        ev_stand = sum(p * evaluate_final_payout(player_total, dt) for dt, p in d_dist.items())
        
        # Batasan kedalaman pencarian dipatok pada tingkat kedalaman rendah agar demo responsif
        ev_hit = backtrack_player_hit_dfs(player_total, 0, dealer_upcard, card_counts, depth=0, max_depth=2)
        
        recommendation = "STAND" if ev_stand >= ev_hit else "HIT"
        return recommendation, max(ev_stand, ev_hit)

    @staticmethod
    def solve_via_monte_carlo(shoe, player_total, dealer_upcard, iterations=10000):
        """Menghitung rasio peluang kemenangan empiris melalui sampling acak masif."""
        stand_wins = 0
        flat_deck_base = []
        for v, count in shoe.cards.items():
            flat_deck_base.extend([v] * count)
            
        # Lintasan Playout Opsi STAND
        for _ in range(iterations):
            deck_copy = flat_deck_base.copy()
            random.shuffle(deck_copy)
            
            d_total = dealer_upcard
            d_soft = 1 if dealer_upcard == 11 else 0
            while d_total < 17 and deck_copy:
                c = deck_copy.pop()
                d_total, d_soft = add_card_points(d_total, d_soft, c)
                
            payout = evaluate_final_payout(player_total, d_total)
            if payout > 0: stand_wins += 1
            elif payout == 0: stand_wins += 0.5
                
        # Lintasan Playout Opsi HIT (Wajib menarik kartu pertama sekali)
        hit_wins = 0
        for _ in range(iterations):
            deck_copy = flat_deck_base.copy()
            random.shuffle(deck_copy)
            
            if not deck_copy: continue
            c = deck_copy.pop()
            p_total, p_soft = add_card_points(player_total, 0, c)
            
            if p_total > 21: continue
                
            # Simulasi keputusan lanjutan otomatis berbasis threshold rasional standar
            while p_total < 17 and deck_copy:
                c = deck_copy.pop()
                p_total, p_soft = add_card_points(p_total, p_soft, c)
                
            if p_total > 21: continue
                
            d_total = dealer_upcard
            d_soft = 1 if dealer_upcard == 11 else 0
            while d_total < 17 and deck_copy:
                c = deck_copy.pop()
                d_total, d_soft = add_card_points(d_total, d_soft, c)
                
            payout = evaluate_final_payout(p_total, d_total)
            if payout > 0: hit_wins += 1
            elif payout == 0: hit_wins += 0.5
                
        prob_stand = stand_wins / iterations
        prob_hit = hit_wins / iterations
        recommendation = "STAND" if prob_stand >= prob_hit else "HIT"
        return recommendation, max(prob_stand, prob_hit)


# --- DRIVER CODE & BENCHMARKING FUNCTION ---

if __name__ == '__main__':
    print("=========================================================================")
    print("SIMULASI BENCHMARK ALGORITMA BLACKJACK - PROYEK AKHIR ASA INFORMATIKA")
    print("=========================================================================")
    
    # 1. Bangun Objek Wadah Kartu (8 Dek standar)
    shoe = BlackjackShoe(num_decks=8, penetration_limit=0.75)
    
    # 2. Inisialisasi Skenario Pengujian: Sisa 4 dek dengan kondisi True Count +3 [Spesifikasi Driver Code]
    target_remaining_decks = 4
    target_true_count = 3.0
    shoe.set_custom_shoe(remaining_decks=target_remaining_decks, desired_true_count=target_true_count)
    
    # Snapshot State Profil Masalah
    player_test_total = 14
    dealer_test_upcard = 10
    
    print(f"[Shoe Setup] Sisa Dek: {target_remaining_decks} dek | Aturan Reshuffle: Kritis Penetrasi 75%")
    print(f"[State Profile] Skor Pemain: {player_test_total} | Kartu Terbuka Dealer: {dealer_test_upcard}")
    print(f"[Count Status] Current Shoe Running Count: {shoe.running_count} | Target True Count: {shoe.get_true_count():+.2f}")
    print("-------------------------------------------------------------------------\n")
    
    # UJI MODEL 1: DYNAMIC PROGRAMMING
    t_start = time.perf_counter()
    dp_rec, dp_val = BlackjackSolver.solve_via_dynamic_programming(shoe, player_test_total, dealer_test_upcard)
    dp_time = (time.perf_counter() - t_start) * 1000
    print(f"1. ALGORITMA DYNAMIC PROGRAMMING (Rekursi + Memoisasi)")
    print(f"   - Hasil Rekomendasi : {dp_rec}")
    print(f"   - Expected Value   : {dp_val:.4f}")
    print(f"   - Waktu Komputasi   : {dp_time:.4f} milidetik\n")
    
    # UJI MODEL 2: BACKTRACKING (DFS PURE)
    t_start = time.perf_counter()
    bt_rec, bt_val = BlackjackSolver.solve_via_backtracking(shoe, player_test_total, dealer_test_upcard)
    bt_time = (time.perf_counter() - t_start) * 1000
    print(f"2. ALGORITMA BACKTRACKING (Pencarian DFS Murni dengan Pruning)")
    print(f"   - Hasil Rekomendasi : {bt_rec}")
    print(f"   - Expected Value   : {bt_val:.4f}")
    print(f"   - Waktu Komputasi   : {bt_time:.4f} milidetik\n")
    
    # UJI MODEL 3: SIMULASI MONTE CARLO
    t_start = time.perf_counter()
    mc_rec, mc_val = BlackjackSolver.solve_via_monte_carlo(shoe, player_test_total, dealer_test_upcard, iterations=10000)
    mc_time = (time.perf_counter() - t_start) * 1000
    print(f"3. SIMULASI MONTE CARLO (10.000 Iterasi Playouts Acak)")
    print(f"   - Hasil Rekomendasi : {mc_rec}")
    print(f"   - Win Rate Empiris : {mc_val:.4f}")
    print(f"   - Waktu Komputasi   : {mc_time:.4f} milidetik\n")
    print("=========================================================================")