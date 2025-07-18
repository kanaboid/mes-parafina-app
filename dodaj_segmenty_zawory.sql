-- Dodanie nowych segmentów i zaworów do bazy danych MES
-- Strefa czysta - segmenty i zawory z pliku segmenty_202507160010.md

-- START TRANSACTION;

-- ========================================
-- 1. DODANIE NOWYCH WĘZŁÓW RUROCIĄGU
-- ========================================

-- Węzły dla beczek czystych (wejściowe)
INSERT IGNORE INTO `wezly_rurociagu` (`nazwa_wezla`) VALUES
('w_b1c_in'),
('w_b2c_in'),
('w_b3c_in'),
('w_b4c_in'),
('w_b5c_in'),
('w_b6c_in'),
('w_b7c_in'),
('w_b8c_in'),
('w_b9c_in'),
('w_b10c_in'),
('w_b11c_in'),
('w_b12c_in');

-- Węzły dla beczek czystych (wyjściowe)
INSERT IGNORE INTO `wezly_rurociagu` (`nazwa_wezla`) VALUES
('w_b1c_out'),
('w_b2c_out'),
('w_b3c_out'),
('w_b4c_out'),
('w_b5c_out'),
('w_b6c_out'),
('w_b7c_out'),
('w_b8c_out'),
('w_b9c_out'),
('w_b10c_out'),
('w_b11c_out'),
('w_b12c_out');

-- Węzły grupowe
INSERT IGNORE INTO `wezly_rurociagu` (`nazwa_wezla`) VALUES
('w_b2c_b1c_in'),
('w_b4c_b3c_b2c_b1c_in');

-- Węzły dla systemu pomp mieszanki
INSERT IGNORE INTO `wezly_rurociagu` (`nazwa_wezla`) VALUES
('w_pompa_mieszanki_rurociag'),
('w_pompa_mieszanki_down'),
('w_pompa_mieszanki_up');

-- Węzły dla systemu pomp B12c
INSERT IGNORE INTO `wezly_rurociagu` (`nazwa_wezla`) VALUES
('w_pompa_b12c'),
('biala_out'),
('cysterna_b12c_out'),
('cysterna_b12c_in');

-- Węzeł dla oczyszczalni
INSERT IGNORE INTO `wezly_rurociagu` (`nazwa_wezla`) VALUES
('w_fz_fn_oczyszczalnia');

-- ========================================
-- 2. DODANIE NOWYCH ZAWORÓW
-- ========================================

INSERT IGNORE INTO `zawory` (`nazwa_zaworu`, `stan`) VALUES
('v_w_b9c_w_pompa_mieszanki_down', 'ZAMKNIETY'),
('v_w_b8c_w_pompa_mieszanki_down', 'ZAMKNIETY'),
('v_w_pompa_mieszanki_down_w_pompa_mieszanki_up', 'ZAMKNIETY'),
('v_w_pompa_mieszanki_rurociag_w_pompa_mieszanki_down', 'ZAMKNIETY'),
('v_w_pompa_mieszanki_up_w_b9c_in', 'ZAMKNIETY'),
('v_w_pompa_mieszanki_up_w_b8c_in', 'ZAMKNIETY'),
('v_w_fz_fn_oczyszczalnia_w_pompa_mieszanki_up', 'ZAMKNIETY'),
('v_w_b10c_out_w_pompa_mieszanki_rurociag', 'ZAMKNIETY'),
('v_w_b7c_out_w_pompa_mieszanki_rurociag', 'ZAMKNIETY'),
('v_w_b12c_out_w_pompa_b12c', 'ZAMKNIETY'),
('v_biala_out_w_pompa_b12c', 'ZAMKNIETY'),
('v_cysterna_b12c_out_w_pompa_b12c', 'ZAMKNIETY'),
('v_w_pompa_b12c_cysterna_b12c_in', 'ZAMKNIETY'),
('v_w_b4c_b3c_b2c_b1c_in_b3c_in', 'ZAMKNIETY'),
('v_w_b4c_b3c_b2c_b1c_in_w_b2c_b1c_in', 'ZAMKNIETY'),
('v_w_b2c_b1c_in_b2c_in', 'ZAMKNIETY'),
('v_w_b2c_b1c_in_b1c_in', 'ZAMKNIETY');

-- ========================================
-- 3. DODANIE NOWYCH SEGMENTÓW
-- ========================================

-- Segmenty systemu pomp mieszanki
INSERT IGNORE INTO `segmenty` (`nazwa_segmentu`, `id_wezla_startowego`, `id_wezla_koncowego`, `id_zaworu`) VALUES
('segm_w_b9c_w_pompa_mieszanki_down', 
 (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b9c_out'),
 (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_pompa_mieszanki_down'),
 (SELECT id FROM zawory WHERE nazwa_zaworu = 'v_w_b9c_w_pompa_mieszanki_down')),

('segm_w_b8c_w_pompa_mieszanki_down', 
 (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b8c_out'),
 (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_pompa_mieszanki_down'),
 (SELECT id FROM zawory WHERE nazwa_zaworu = 'v_w_b8c_w_pompa_mieszanki_down')),

('segm_w_pompa_mieszanki_down_w_pompa_mieszanki_up', 
 (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_pompa_mieszanki_down'),
 (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_pompa_mieszanki_up'),
 (SELECT id FROM zawory WHERE nazwa_zaworu = 'v_w_pompa_mieszanki_down_w_pompa_mieszanki_up')),

('segm_w_pompa_mieszanki_rurociag_w_pompa_mieszanki_down', 
 (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_pompa_mieszanki_rurociag'),
 (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_pompa_mieszanki_down'),
 (SELECT id FROM zawory WHERE nazwa_zaworu = 'v_w_pompa_mieszanki_rurociag_w_pompa_mieszanki_down')),

('segm_w_pompa_mieszanki_up_w_b9c_in', 
 (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_pompa_mieszanki_up'),
 (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b9c_in'),
 (SELECT id FROM zawory WHERE nazwa_zaworu = 'v_w_pompa_mieszanki_up_w_b9c_in')),

('segm_w_pompa_mieszanki_up_w_b8c_in', 
 (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_pompa_mieszanki_up'),
 (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b8c_in'),
 (SELECT id FROM zawory WHERE nazwa_zaworu = 'v_w_pompa_mieszanki_up_w_b8c_in')),

('segm_w_fz_fn_oczyszczalnia_w_pompa_mieszanki_up', 
 (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_fz_fn_oczyszczalnia'),
 (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_pompa_mieszanki_up'),
 (SELECT id FROM zawory WHERE nazwa_zaworu = 'v_w_fz_fn_oczyszczalnia_w_pompa_mieszanki_up')),

('segm_w_b10c_out_w_pompa_mieszanki_rurociag', 
 (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b10c_out'),
 (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_pompa_mieszanki_rurociag'),
 (SELECT id FROM zawory WHERE nazwa_zaworu = 'v_w_b10c_out_w_pompa_mieszanki_rurociag')),

('segm_w_b7c_out_w_pompa_mieszanki_rurociag', 
 (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b7c_out'),
 (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_pompa_mieszanki_rurociag'),
 (SELECT id FROM zawory WHERE nazwa_zaworu = 'v_w_b7c_out_w_pompa_mieszanki_rurociag'));

-- Segmenty systemu pomp B12c
INSERT IGNORE INTO `segmenty` (`nazwa_segmentu`, `id_wezla_startowego`, `id_wezla_koncowego`, `id_zaworu`) VALUES
('segm_w_b12c_out_w_pompa_b12c', 
 (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b12c_out'),
 (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_pompa_b12c'),
 (SELECT id FROM zawory WHERE nazwa_zaworu = 'v_w_b12c_out_w_pompa_b12c')),

('segm_biala_out_w_pompa_b12c', 
 (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'biala_out'),
 (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_pompa_b12c'),
 (SELECT id FROM zawory WHERE nazwa_zaworu = 'v_biala_out_w_pompa_b12c')),

('segm_cysterna_b12c_out_w_pompa_b12c', 
 (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'cysterna_b12c_out'),
 (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_pompa_b12c'),
 (SELECT id FROM zawory WHERE nazwa_zaworu = 'v_cysterna_b12c_out_w_pompa_b12c')),

('segm_w_pompa_b12c_cysterna_b12c_in', 
 (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_pompa_b12c'),
 (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'cysterna_b12c_in'),
 (SELECT id FROM zawory WHERE nazwa_zaworu = 'v_w_pompa_b12c_cysterna_b12c_in'));

-- Segmenty węzłów grupowych
INSERT IGNORE INTO `segmenty` (`nazwa_segmentu`, `id_wezla_startowego`, `id_portu_koncowego`, `id_zaworu`) VALUES
('segm_w_b4c_b3c_b2c_b1c_in_b3c_in', 
 (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b4c_b3c_b2c_b1c_in'),
 (SELECT id FROM porty_sprzetu WHERE nazwa_portu = 'B3c_IN'),
 (SELECT id FROM zawory WHERE nazwa_zaworu = 'v_w_b4c_b3c_b2c_b1c_in_b3c_in')),

('segm_w_b4c_b3c_b2c_b1c_in_w_b2c_b1c_in', 
 (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b4c_b3c_b2c_b1c_in'),
 (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b2c_b1c_in'),
 (SELECT id FROM zawory WHERE nazwa_zaworu = 'v_w_b4c_b3c_b2c_b1c_in_w_b2c_b1c_in')),

('segm_w_b2c_b1c_in_b2c_in', 
 (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b2c_b1c_in'),
 (SELECT id FROM porty_sprzetu WHERE nazwa_portu = 'B2c_IN'),
 (SELECT id FROM zawory WHERE nazwa_zaworu = 'v_w_b2c_b1c_in_b2c_in')),

('segm_w_b2c_b1c_in_b1c_in', 
 (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b2c_b1c_in'),
 (SELECT id FROM porty_sprzetu WHERE nazwa_portu = 'B1c_IN'),
 (SELECT id FROM zawory WHERE nazwa_zaworu = 'v_w_b2c_b1c_in_b1c_in'));

-- COMMIT;

-- ========================================
-- PODSUMOWANIE
-- ========================================
-- Dodano:
-- - 29 nowych węzłów rurociągu
-- - 17 nowych zaworów
-- - 17 nowych segmentów
-- 
-- Segmenty łączą węzły rurociągu i porty sprzętu zgodnie z topologią strefy czystej
-- Każdy segment ma przypisany zawór kontrolujący przepływ
-- Wszystkie zawory są domyślnie zamknięte (ZAMKNIETY) 