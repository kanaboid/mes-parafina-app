-- KOMPLETNA TOPOLOGIA STREFY CZYSTEJ
-- Na podstawie zaktualizowanego diagramu topologia.drawio - strefa_czysta
-- Uwzględnia wszystkie 12 beczek czystych (B1c-B12c) oraz segmenty dwukierunkowe

-- ==============================================
-- WĘZŁY RUROCIĄGU - WSZYSTKIE Z DIAGRAMU
-- ==============================================
INSERT INTO `wezly_rurociagu` (`nazwa_wezla`) VALUES
-- Węzły dla beczki B12c
('w_b12c_in'),
('w_b12c_out'),
-- Węzły dla beczki B11c
('w_b11c_in'),
('w_b11c_out'),
-- Węzły dla beczki B10c
('w_b10c_in'),
('w_b10c_out'),
-- Węzły dla beczek B9c i B8c
('w_b9c_in'),
('w_b9c_out'),
('w_b8c_in'),
('w_b8c_out'),
-- Węzły dla beczki B7c
('w_b7c_in'),
('w_b7c_out'),
-- Węzły dla beczki B6c
('w_b6c_in'),
('w_b6c_out'),
-- Węzły dla beczki B5c
('w_b5c_in'),
('w_b5c_out'),
-- Węzły dla beczki B4c
('w_b4c_in'),
('w_b4c_out'),
-- Węzły dla beczki B3c
('w_b3c_in'),
('w_b3c_out'),
-- Węzły dla beczki B2c
('w_b2c_in'),
('w_b2c_out'),
-- Węzły dla beczki B1c
('w_b1c_in'),
('w_b1c_out'),
-- Węzły grupowe (z diagramu)
('w_b4c_b3c_b2c_b1c_in'),
('w_b2c_b1c_in'),
-- Węzły systemu pomp
('w_pompa_b12c'),
('w_pompa_mieszanki_down'),
('w_pompa_mieszanki_up'),
('w_pompa_mieszanki_rurociag'),
-- Węzeł oczyszczalni
('w_fz_fn_oczyszczalnia');

-- ==============================================
-- ZAWORY DLA STREFY CZYSTEJ
-- ==============================================
INSERT INTO `zawory` (`nazwa_zaworu`, `stan`) VALUES
-- Zawory dla beczki B12c
('V_B12c_OUT_W_B12c_OUT', 'ZAMKNIETY'),
('V_W_B12c_IN_B12c_IN', 'ZAMKNIETY'),
-- Zawory dla beczki B11c
('V_B11c_OUT_W_B11c_OUT', 'ZAMKNIETY'),
('V_W_B11c_IN_B11c_IN', 'ZAMKNIETY'),
-- Zawory dla beczki B10c
('V_B10c_OUT_W_B10c_OUT', 'ZAMKNIETY'),
('V_W_B10c_IN_B10c_IN', 'ZAMKNIETY'),
-- Zawory dla beczki B9c
('V_B9c_OUT_W_B9c_OUT', 'ZAMKNIETY'),
('V_W_B9c_IN_B9c_IN', 'ZAMKNIETY'),
-- Zawory dla beczki B8c
('V_B8c_OUT_W_B8c_OUT', 'ZAMKNIETY'),
('V_W_B8c_IN_B8c_IN', 'ZAMKNIETY'),
-- Zawory dla beczki B7c
('V_B7c_OUT_W_B7c_OUT', 'ZAMKNIETY'),
('V_W_B7c_IN_B7c_IN', 'ZAMKNIETY'),
-- Zawory dla beczki B6c
('V_B6c_OUT_W_B6c_OUT', 'ZAMKNIETY'),
('V_W_B6c_IN_B6c_IN', 'ZAMKNIETY'),
-- Zawory dla beczki B5c
('V_B5c_OUT_W_B5c_OUT', 'ZAMKNIETY'),
('V_W_B5c_IN_B5c_IN', 'ZAMKNIETY'),
-- Zawory dla beczki B4c
('V_B4c_OUT_W_B4c_OUT', 'ZAMKNIETY'),
('V_W_B4c_IN_B4c_IN', 'ZAMKNIETY'),
-- Zawory dla beczki B3c
('V_B3c_OUT_W_B3c_OUT', 'ZAMKNIETY'),
('V_W_B3c_IN_B3c_IN', 'ZAMKNIETY'),
-- Zawory dla beczki B2c
('V_B2c_OUT_W_B2c_OUT', 'ZAMKNIETY'),
('V_W_B2c_IN_B2c_IN', 'ZAMKNIETY'),
-- Zawory dla beczki B1c
('V_B1c_OUT_W_B1c_OUT', 'ZAMKNIETY'),
('V_W_B1c_IN_B1c_IN', 'ZAMKNIETY'),
-- Zawory magistrali poziomej (OUT) - DWUKIERUNKOWE
('V_W_B12c_OUT_W_B11c_OUT', 'ZAMKNIETY'),
('V_W_B11c_OUT_W_B10c_OUT', 'ZAMKNIETY'),
('V_W_B10c_OUT_W_B9c_OUT', 'ZAMKNIETY'),
('V_W_B9c_OUT_W_B8c_OUT', 'ZAMKNIETY'),
('V_W_B8c_OUT_W_B7c_OUT', 'ZAMKNIETY'),
('V_W_B7c_OUT_W_B6c_OUT', 'ZAMKNIETY'),
('V_W_B6c_OUT_W_B5c_OUT', 'ZAMKNIETY'),
('V_W_B5c_OUT_W_B4c_OUT', 'ZAMKNIETY'),
('V_W_B4c_OUT_W_B3c_OUT', 'ZAMKNIETY'),
('V_W_B3c_OUT_W_B2c_OUT', 'ZAMKNIETY'),
('V_W_B2c_OUT_W_B1c_OUT', 'ZAMKNIETY'),
-- Zawory magistrali poziomej (IN) - DWUKIERUNKOWE
('V_W_B12c_IN_W_B11c_IN', 'ZAMKNIETY'),
('V_W_B11c_IN_W_B10c_IN', 'ZAMKNIETY'),
('V_W_B10c_IN_W_B9c_IN', 'ZAMKNIETY'),
('V_W_B9c_IN_W_B8c_IN', 'ZAMKNIETY'),
('V_W_B8c_IN_W_B7c_IN', 'ZAMKNIETY'),
('V_W_B7c_IN_W_B6c_IN', 'ZAMKNIETY'),
('V_W_B6c_IN_W_B5c_IN', 'ZAMKNIETY'),
('V_W_B5c_IN_W_B4c_IN', 'ZAMKNIETY'),
('V_W_B4c_IN_W_B3c_IN', 'ZAMKNIETY'),
('V_W_B3c_IN_W_B2c_IN', 'ZAMKNIETY'),
('V_W_B2c_IN_W_B1c_IN', 'ZAMKNIETY'),
-- Zawory węzłów grupowych
('V_W_B4c_B3c_B2c_B1c_IN_W_B4c_IN', 'ZAMKNIETY'),
('V_W_B4c_B3c_B2c_B1c_IN_W_B2c_B1c_IN', 'ZAMKNIETY'),
('V_W_B2c_B1c_IN_W_B2c_IN', 'ZAMKNIETY'),
('V_W_B2c_B1c_IN_W_B1c_IN', 'ZAMKNIETY'),
-- Zawory systemu pomp B12c
('V_W_POMPA_B12c_W_B12c_IN', 'ZAMKNIETY'),
('V_CYSTERNA_B12c_W_POMPA_B12c', 'ZAMKNIETY'),
('V_BIALA_W_POMPA_B12c', 'ZAMKNIETY'),
-- Zawory systemu pomp mieszanki
('V_W_B9c_OUT_W_POMPA_MIESZANKI_RUROCIAG', 'ZAMKNIETY'),
('V_W_B8c_OUT_W_POMPA_MIESZANKI_RUROCIAG', 'ZAMKNIETY'),
('V_W_POMPA_MIESZANKI_RUROCIAG_W_POMPA_MIESZANKI_DOWN', 'ZAMKNIETY'),
('V_W_POMPA_MIESZANKI_DOWN_W_POMPA_MIESZANKI_UP', 'ZAMKNIETY'),
('V_W_POMPA_MIESZANKI_UP_W_B9c_IN', 'ZAMKNIETY'),
('V_W_POMPA_MIESZANKI_UP_W_B8c_IN', 'ZAMKNIETY'),
-- Zawory oczyszczalni
('V_W_POMPA_MIESZANKI_UP_W_FZ_FN_OCZYSZCZALNIA', 'ZAMKNIETY'),
('V_W_FZ_FN_OCZYSZCZALNIA_ZEWNETRZNE', 'ZAMKNIETY');

-- ==============================================
-- SEGMENTY WYJŚCIOWE Z BECZEK (PORT -> WĘZEŁ)
-- ==============================================
INSERT INTO `segmenty` (`nazwa_segmentu`, `id_portu_startowego`, `id_wezla_koncowego`, `id_zaworu`) VALUES
('SEGM_B12c_OUT_W_B12c_OUT', 84, (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b12c_out'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_B12c_OUT_W_B12c_OUT')),
('SEGM_B11c_OUT_W_B11c_OUT', 83, (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b11c_out'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_B11c_OUT_W_B11c_OUT')),
('SEGM_B10c_OUT_W_B10c_OUT', 82, (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b10c_out'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_B10c_OUT_W_B10c_OUT')),
('SEGM_B9c_OUT_W_B9c_OUT', 81, (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b9c_out'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_B9c_OUT_W_B9c_OUT')),
('SEGM_B8c_OUT_W_B8c_OUT', 80, (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b8c_out'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_B8c_OUT_W_B8c_OUT')),
('SEGM_B7c_OUT_W_B7c_OUT', 79, (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b7c_out'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_B7c_OUT_W_B7c_OUT')),
('SEGM_B6c_OUT_W_B6c_OUT', 78, (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b6c_out'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_B6c_OUT_W_B6c_OUT')),
('SEGM_B5c_OUT_W_B5c_OUT', 77, (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b5c_out'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_B5c_OUT_W_B5c_OUT')),
('SEGM_B4c_OUT_W_B4c_OUT', 76, (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b4c_out'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_B4c_OUT_W_B4c_OUT')),
('SEGM_B3c_OUT_W_B3c_OUT', 75, (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b3c_out'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_B3c_OUT_W_B3c_OUT')),
('SEGM_B2c_OUT_W_B2c_OUT', 74, (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b2c_out'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_B2c_OUT_W_B2c_OUT')),
('SEGM_B1c_OUT_W_B1c_OUT', 73, (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b1c_out'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_B1c_OUT_W_B1c_OUT'));

-- ==============================================
-- SEGMENTY WEJŚCIOWE DO BECZEK (WĘZEŁ -> PORT)
-- ==============================================
INSERT INTO `segmenty` (`nazwa_segmentu`, `id_wezla_startowego`, `id_portu_koncowego`, `id_zaworu`) VALUES
('SEGM_W_B12c_IN_B12c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b12c_in'), 69, (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B12c_IN_B12c_IN')),
('SEGM_W_B11c_IN_B11c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b11c_in'), 68, (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B11c_IN_B11c_IN')),
('SEGM_W_B10c_IN_B10c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b10c_in'), 67, (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B10c_IN_B10c_IN')),
('SEGM_W_B9c_IN_B9c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b9c_in'), 66, (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B9c_IN_B9c_IN')),
('SEGM_W_B8c_IN_B8c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b8c_in'), 65, (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B8c_IN_B8c_IN')),
('SEGM_W_B7c_IN_B7c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b7c_in'), 64, (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B7c_IN_B7c_IN')),
('SEGM_W_B6c_IN_B6c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b6c_in'), 63, (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B6c_IN_B6c_IN')),
('SEGM_W_B5c_IN_B5c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b5c_in'), 62, (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B5c_IN_B5c_IN')),
('SEGM_W_B4c_IN_B4c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b4c_in'), 61, (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B4c_IN_B4c_IN')),
('SEGM_W_B3c_IN_B3c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b3c_in'), 60, (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B3c_IN_B3c_IN')),
('SEGM_W_B2c_IN_B2c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b2c_in'), 59, (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B2c_IN_B2c_IN')),
('SEGM_W_B1c_IN_B1c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b1c_in'), 58, (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B1c_IN_B1c_IN'));

-- ==============================================
-- SEGMENTY MAGISTRALI POZIOMEJ (OUT) - DWUKIERUNKOWE
-- ==============================================
INSERT INTO `segmenty` (`nazwa_segmentu`, `id_wezla_startowego`, `id_wezla_koncowego`, `id_zaworu`) VALUES
('SEGM_W_B12c_OUT_W_B11c_OUT', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b12c_out'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b11c_out'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B12c_OUT_W_B11c_OUT')),
('SEGM_W_B11c_OUT_W_B12c_OUT', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b11c_out'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b12c_out'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B12c_OUT_W_B11c_OUT')),
('SEGM_W_B11c_OUT_W_B10c_OUT', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b11c_out'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b10c_out'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B11c_OUT_W_B10c_OUT')),
('SEGM_W_B10c_OUT_W_B11c_OUT', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b10c_out'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b11c_out'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B11c_OUT_W_B10c_OUT')),
('SEGM_W_B10c_OUT_W_B9c_OUT', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b10c_out'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b9c_out'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B10c_OUT_W_B9c_OUT')),
('SEGM_W_B9c_OUT_W_B10c_OUT', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b9c_out'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b10c_out'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B10c_OUT_W_B9c_OUT')),
('SEGM_W_B9c_OUT_W_B8c_OUT', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b9c_out'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b8c_out'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B9c_OUT_W_B8c_OUT')),
('SEGM_W_B8c_OUT_W_B9c_OUT', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b8c_out'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b9c_out'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B9c_OUT_W_B8c_OUT')),
('SEGM_W_B8c_OUT_W_B7c_OUT', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b8c_out'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b7c_out'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B8c_OUT_W_B7c_OUT')),
('SEGM_W_B7c_OUT_W_B8c_OUT', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b7c_out'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b8c_out'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B8c_OUT_W_B7c_OUT')),
('SEGM_W_B7c_OUT_W_B6c_OUT', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b7c_out'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b6c_out'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B7c_OUT_W_B6c_OUT')),
('SEGM_W_B6c_OUT_W_B7c_OUT', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b6c_out'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b7c_out'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B7c_OUT_W_B6c_OUT')),
('SEGM_W_B6c_OUT_W_B5c_OUT', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b6c_out'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b5c_out'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B6c_OUT_W_B5c_OUT')),
('SEGM_W_B5c_OUT_W_B6c_OUT', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b5c_out'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b6c_out'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B6c_OUT_W_B5c_OUT')),
('SEGM_W_B5c_OUT_W_B4c_OUT', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b5c_out'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b4c_out'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B5c_OUT_W_B4c_OUT')),
('SEGM_W_B4c_OUT_W_B5c_OUT', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b4c_out'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b5c_out'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B5c_OUT_W_B4c_OUT')),
('SEGM_W_B4c_OUT_W_B3c_OUT', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b4c_out'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b3c_out'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B4c_OUT_W_B3c_OUT')),
('SEGM_W_B3c_OUT_W_B4c_OUT', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b3c_out'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b4c_out'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B4c_OUT_W_B3c_OUT')),
('SEGM_W_B3c_OUT_W_B2c_OUT', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b3c_out'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b2c_out'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B3c_OUT_W_B2c_OUT')),
('SEGM_W_B2c_OUT_W_B3c_OUT', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b2c_out'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b3c_out'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B3c_OUT_W_B2c_OUT')),
('SEGM_W_B2c_OUT_W_B1c_OUT', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b2c_out'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b1c_out'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B2c_OUT_W_B1c_OUT')),
('SEGM_W_B1c_OUT_W_B2c_OUT', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b1c_out'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b2c_out'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B2c_OUT_W_B1c_OUT'));

-- ==============================================
-- SEGMENTY MAGISTRALI POZIOMEJ (IN) - DWUKIERUNKOWE
-- ==============================================
INSERT INTO `segmenty` (`nazwa_segmentu`, `id_wezla_startowego`, `id_wezla_koncowego`, `id_zaworu`) VALUES
('SEGM_W_B12c_IN_W_B11c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b12c_in'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b11c_in'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B12c_IN_W_B11c_IN')),
('SEGM_W_B11c_IN_W_B12c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b11c_in'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b12c_in'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B12c_IN_W_B11c_IN')),
('SEGM_W_B11c_IN_W_B10c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b11c_in'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b10c_in'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B11c_IN_W_B10c_IN')),
('SEGM_W_B10c_IN_W_B11c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b10c_in'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b11c_in'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B11c_IN_W_B10c_IN')),
('SEGM_W_B10c_IN_W_B9c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b10c_in'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b9c_in'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B10c_IN_W_B9c_IN')),
('SEGM_W_B9c_IN_W_B10c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b9c_in'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b10c_in'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B10c_IN_W_B9c_IN')),
('SEGM_W_B9c_IN_W_B8c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b9c_in'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b8c_in'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B9c_IN_W_B8c_IN')),
('SEGM_W_B8c_IN_W_B9c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b8c_in'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b9c_in'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B9c_IN_W_B8c_IN')),
('SEGM_W_B8c_IN_W_B7c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b8c_in'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b7c_in'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B8c_IN_W_B7c_IN')),
('SEGM_W_B7c_IN_W_B8c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b7c_in'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b8c_in'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B8c_IN_W_B7c_IN')),
('SEGM_W_B7c_IN_W_B6c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b7c_in'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b6c_in'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B7c_IN_W_B6c_IN')),
('SEGM_W_B6c_IN_W_B7c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b6c_in'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b7c_in'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B7c_IN_W_B6c_IN')),
('SEGM_W_B6c_IN_W_B5c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b6c_in'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b5c_in'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B6c_IN_W_B5c_IN')),
('SEGM_W_B5c_IN_W_B6c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b5c_in'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b6c_in'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B6c_IN_W_B5c_IN')),
('SEGM_W_B5c_IN_W_B4c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b5c_in'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b4c_in'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B5c_IN_W_B4c_IN')),
('SEGM_W_B4c_IN_W_B5c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b4c_in'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b5c_in'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B5c_IN_W_B4c_IN')),
('SEGM_W_B4c_IN_W_B3c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b4c_in'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b3c_in'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B4c_IN_W_B3c_IN')),
('SEGM_W_B3c_IN_W_B4c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b3c_in'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b4c_in'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B4c_IN_W_B3c_IN')),
('SEGM_W_B3c_IN_W_B2c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b3c_in'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b2c_in'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B3c_IN_W_B2c_IN')),
('SEGM_W_B2c_IN_W_B3c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b2c_in'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b3c_in'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B3c_IN_W_B2c_IN')),
('SEGM_W_B2c_IN_W_B1c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b2c_in'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b1c_in'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B2c_IN_W_B1c_IN')),
('SEGM_W_B1c_IN_W_B2c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b1c_in'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b2c_in'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B2c_IN_W_B1c_IN'));

-- ==============================================
-- SEGMENTY WĘZŁÓW GRUPOWYCH (z diagramu)
-- ==============================================
INSERT INTO `segmenty` (`nazwa_segmentu`, `id_wezla_startowego`, `id_wezla_koncowego`, `id_zaworu`) VALUES
('SEGM_W_B4c_B3c_B2c_B1c_IN_W_B4c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b4c_b3c_b2c_b1c_in'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b4c_in'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B4c_B3c_B2c_B1c_IN_W_B4c_IN')),
('SEGM_W_B4c_B3c_B2c_B1c_IN_W_B2c_B1c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b4c_b3c_b2c_b1c_in'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b2c_b1c_in'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B4c_B3c_B2c_B1c_IN_W_B2c_B1c_IN')),
('SEGM_W_B2c_B1c_IN_W_B2c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b2c_b1c_in'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b2c_in'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B2c_B1c_IN_W_B2c_IN')),
('SEGM_W_B2c_B1c_IN_W_B1c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b2c_b1c_in'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b1c_in'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B2c_B1c_IN_W_B1c_IN'));

-- ==============================================
-- SEGMENTY SYSTEMU POMP B12c
-- ==============================================
INSERT INTO `segmenty` (`nazwa_segmentu`, `id_wezla_startowego`, `id_wezla_koncowego`, `id_zaworu`) VALUES
('SEGM_W_POMPA_B12c_W_B12c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_pompa_b12c'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b12c_in'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_POMPA_B12c_W_B12c_IN'));

-- Segmenty cystern do pompy B12c
INSERT INTO `segmenty` (`nazwa_segmentu`, `id_portu_startowego`, `id_wezla_koncowego`, `id_zaworu`) VALUES
('SEGM_CYSTERNA_B12c_W_POMPA_B12c', 123, (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_pompa_b12c'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_CYSTERNA_B12c_W_POMPA_B12c')),
('SEGM_BIALA_W_POMPA_B12c', 122, (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_pompa_b12c'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_BIALA_W_POMPA_B12c'));

-- ==============================================
-- SEGMENTY SYSTEMU POMP MIESZANKI
-- ==============================================
INSERT INTO `segmenty` (`nazwa_segmentu`, `id_wezla_startowego`, `id_wezla_koncowego`, `id_zaworu`) VALUES
('SEGM_W_B9c_OUT_W_POMPA_MIESZANKI_RUROCIAG', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b9c_out'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_pompa_mieszanki_rurociag'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B9c_OUT_W_POMPA_MIESZANKI_RUROCIAG')),
('SEGM_W_B8c_OUT_W_POMPA_MIESZANKI_RUROCIAG', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b8c_out'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_pompa_mieszanki_rurociag'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B8c_OUT_W_POMPA_MIESZANKI_RUROCIAG')),
('SEGM_W_POMPA_MIESZANKI_RUROCIAG_W_POMPA_MIESZANKI_DOWN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_pompa_mieszanki_rurociag'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_pompa_mieszanki_down'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_POMPA_MIESZANKI_RUROCIAG_W_POMPA_MIESZANKI_DOWN')),
('SEGM_W_POMPA_MIESZANKI_DOWN_W_POMPA_MIESZANKI_UP', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_pompa_mieszanki_down'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_pompa_mieszanki_up'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_POMPA_MIESZANKI_DOWN_W_POMPA_MIESZANKI_UP')),
('SEGM_W_POMPA_MIESZANKI_UP_W_B9c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_pompa_mieszanki_up'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b9c_in'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_POMPA_MIESZANKI_UP_W_B9c_IN')),
('SEGM_W_POMPA_MIESZANKI_UP_W_B8c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_pompa_mieszanki_up'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b8c_in'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_POMPA_MIESZANKI_UP_W_B8c_IN'));

-- ==============================================
-- SEGMENTY OCZYSZCZALNI
-- ==============================================
INSERT INTO `segmenty` (`nazwa_segmentu`, `id_wezla_startowego`, `id_wezla_koncowego`, `id_zaworu`) VALUES
('SEGM_W_POMPA_MIESZANKI_UP_W_FZ_FN_OCZYSZCZALNIA', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_pompa_mieszanki_up'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_fz_fn_oczyszczalnia'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_POMPA_MIESZANKI_UP_W_FZ_FN_OCZYSZCZALNIA')),
('SEGM_W_FZ_FN_OCZYSZCZALNIA_ZEWNETRZNE', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_fz_fn_oczyszczalnia'), NULL, (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_FZ_FN_OCZYSZCZALNIA_ZEWNETRZNE'));

-- ==============================================
-- DODATKOWE PORTY I SPRZĘT (jeśli nie istnieją)
-- ==============================================
INSERT INTO `porty_sprzetu` (`id_sprzetu`, `nazwa_portu`, `typ_portu`) VALUES
(115, 'BIALA_OUT', 'OUT'),        -- ID 122 - cysterna biała
(116, 'CYSTERNA_B12c_OUT', 'OUT'); -- ID 123 - cysterna B12c

INSERT INTO `sprzet` (`nazwa_unikalna`, `typ_sprzetu`, `pojemnosc_kg`, `stan_sprzetu`, `temperatura_aktualna`, `cisnienie_aktualne`, `ostatnia_aktualizacja`) VALUES
('BIALA', 'cysterna', 15000.00, 'Gotowy', 60.00, 0.00, NOW()),
('CYSTERNA_B12c_DODATKOWA', 'cysterna', 20000.00, 'Gotowy', 60.00, 0.00, NOW());

-- ==============================================
-- KOMENTARZ KOŃCOWY
-- ==============================================
-- Ten plik zawiera KOMPLETNĄ topologię strefy czystej:
-- - Wszystkie 12 beczek czystych (B1c-B12c)
-- - Węzły wejściowe i wyjściowe dla każdej beczki
-- - Magistrala pozioma (OUT i IN) z segmentami DWUKIERUNKOWYMI
-- - Węzły grupowe zgodnie z diagramem
-- - System pomp B12c
-- - System pomp mieszanki (B9c/B8c)
-- - Oczyszczalnia
-- - Cysterny (biała i cysterna_b12c)
-- 
-- UWAGA: Segmenty dwukierunkowe używają tego samego zaworu! 