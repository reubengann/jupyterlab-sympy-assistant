1. Change title from "Sympy Equation Library" to just "Library". Also change the shortcut button from "Sympy Library" to an icon.

2. The buttons at the top for adding and converting equations are ugly and don't match the buttons that are on the actual equations, which are much nicer.

3. Add a search filter so that I can search based on name, description, latex, or sympy text. It should be a search box with an x for easy clearing.

4. When refreshing (after adding/editing equation), don't just jump to the top. Try to maintain the same position in the scroll.

5. When editing the sympy in the modal, I can't seem to insert a newline. Hitting enter does nothing while in the text box.

6. `\mathrm{d}{T_{s}} = \frac{\beta v T}{c_{P}} \mathrm{d}{P_{s}}`
    This does not parse correctly. I get
    P_s, T, T_s, beta, c_P, d, mathrm, v = spp.symbols('P_s T T_s beta c_P d mathrm v')
    spp.Eq(T_s*d*mathrm, P_s*T*beta*d*mathrm*v/c_P)

7. `\left(\frac{\partial{c_{v}}}{\partial{v}}\right)_{T} = \left(\frac{\partial{c_{v}}}{\partial{\rho_{r}}}\right)_{T} \left(\frac{\partial{\rho_{r}}}{\partial{v}}\right)_{T}`
    This is parsed as 
    ```
    c_v, rho_r, v = spp.symbols('c_v rho_r v')
    spp.Eq(c_v/v, c_v/rho_r)
    ```

--- undone ---
