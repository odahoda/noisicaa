; TODO:
; - add shortcuts to run tests
; - add tweaks to C++ indentation
;   - no indentation for namespace
;   - correct indentation for arg list continuation

((nil . (
         ; Projetile
         (projectile-project-test-cmd . "bin/runtests")

         (pyvenv-workon . "noisicaa")

         ; Uses spaces for indentation.
         (indent-tabs-mode . nil)

         ; Be more generous than 80 columns.
         (fill-column . 100)

         ; Highlight tabs, so they don't slip in unnoticed.
         ; TODO: make this work correctly
         ; - should only show leading tabs
         ; - disrupts colors in magit
         ;(eval . (add-hook 'font-lock-mode-hook
         ;                  (lambda ()
         ;                    (font-lock-add-keywords
         ;                     nil
         ;                     '(("\t" 0 'trailing-whitespace prepend))))))
         )
      )
 )
